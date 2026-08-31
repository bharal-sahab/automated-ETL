"""SQLite connection manager (SQLModel) for a local pipeline.db file."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import event, func
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from core.config import Settings
from core.errors import DatabaseError
from db.models import (
    ProcessedMetricInsert,
    ProcessedMetrics,
    RawIngestion,
    RawIngestionInsert,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def normalize_database_url(url: str) -> str:
    """Accept sqlite or sqlite+aiosqlite URLs; always return a sync sqlite URL."""
    stripped = url.strip()
    if not stripped:
        raise DatabaseError("database_url must not be empty")
    if stripped.startswith("sqlite+aiosqlite://"):
        rest = stripped.removeprefix("sqlite+aiosqlite://")
        return f"sqlite://{rest}"
    return stripped


def is_memory_url(url: str) -> bool:
    return ":memory:" in normalize_database_url(url)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: Any, _connection_record: Any) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class DatabaseClient:
    """Lifespan-managed SQLite engine. Creates `pipeline.db` (or :memory:) tables on connect.

    SQLModel sessions are synchronous; public methods stay async via `asyncio.to_thread`.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: Engine | None = None
        self._normalized_url: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    @property
    def database_url(self) -> str:
        return self._normalized_url or normalize_database_url(self._settings.database_url)

    async def connect(self) -> None:
        if self.is_connected:
            return
        try:
            await asyncio.to_thread(self._connect_sync)
        except DatabaseError:
            raise
        except Exception as exc:
            self._engine = None
            self._normalized_url = None
            raise DatabaseError(
                "Failed to connect to SQLite database",
                details={"reason": str(exc), "url": normalize_database_url(self._settings.database_url)},
            ) from exc
        logger.info("SQLite engine connected url=%s", self._normalized_url)

    def _connect_sync(self) -> None:
        url = normalize_database_url(self._settings.database_url)
        engine_kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if is_memory_url(url):
            # One shared in-memory database across sessions (required for :memory:).
            engine_kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **engine_kwargs)
        _enable_sqlite_foreign_keys(engine)
        SQLModel.metadata.create_all(engine)
        self._engine = engine
        self._normalized_url = url

    async def close(self) -> None:
        engine = self._engine
        self._engine = None
        self._normalized_url = None
        if engine is None:
            return
        await asyncio.to_thread(engine.dispose)
        logger.info("SQLite engine closed")

    def _require_engine(self) -> Engine:
        if self._engine is None:
            raise DatabaseError("Database client is not connected")
        return self._engine

    @contextmanager
    def _session(self) -> Iterator[Session]:
        engine = self._require_engine()
        with Session(engine) as session:
            yield session

    async def _run(self, fn: Callable[[], T]) -> T:
        try:
            return await asyncio.to_thread(fn)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError("SQLite operation failed", details={"reason": str(exc)}) from exc

    async def insert_raw_ingestion(self, data: RawIngestionInsert) -> RawIngestion:
        def _insert() -> RawIngestion:
            row = RawIngestion.model_validate({"source": data.source, "payload": data.payload})
            with self._session() as session:
                session.add(row)
                session.commit()
                session.refresh(row)
                session.expunge(row)
            return row

        try:
            return await self._run(_insert)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(
                "Failed to insert raw_ingestion row",
                details={"reason": str(exc)},
            ) from exc

    async def insert_processed_metrics(
        self, rows: list[ProcessedMetricInsert]
    ) -> list[ProcessedMetrics]:
        if not rows:
            return []

        def _insert() -> list[ProcessedMetrics]:
            created = [ProcessedMetrics.model_validate(row.model_dump()) for row in rows]
            with self._session() as session:
                session.add_all(created)
                session.commit()
                for item in created:
                    session.refresh(item)
                    session.expunge(item)
            return created

        try:
            return await self._run(_insert)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(
                "Failed to insert processed_metrics rows",
                details={"reason": str(exc)},
            ) from exc

    async def fetch_processed_metrics(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ProcessedMetrics], int]:
        if limit < 1:
            raise DatabaseError("limit must be >= 1")
        if offset < 0:
            raise DatabaseError("offset must be >= 0")

        def _fetch() -> tuple[list[ProcessedMetrics], int]:
            with self._session() as session:
                total = session.exec(select(func.count()).select_from(ProcessedMetrics)).one()
                items = list(
                    session.exec(
                        select(ProcessedMetrics)
                        .order_by(ProcessedMetrics.processed_at.desc(), ProcessedMetrics.id.desc())
                        .offset(offset)
                        .limit(limit)
                    ).all()
                )
                for item in items:
                    session.expunge(item)
            return items, int(total)

        try:
            return await self._run(_fetch)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(
                "Failed to fetch processed_metrics",
                details={"reason": str(exc)},
            ) from exc

    async def fetch_processed_metrics_by_run(self, run_id: UUID) -> list[ProcessedMetrics]:
        def _fetch() -> list[ProcessedMetrics]:
            with self._session() as session:
                items = list(
                    session.exec(
                        select(ProcessedMetrics)
                        .where(ProcessedMetrics.run_id == run_id)
                        .order_by(ProcessedMetrics.post_id)
                    ).all()
                )
                for item in items:
                    session.expunge(item)
            return items

        try:
            return await self._run(_fetch)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(
                "Failed to fetch processed_metrics by run_id",
                details={"reason": str(exc)},
            ) from exc

    async def get_raw_ingestion(self, run_id: UUID) -> RawIngestion | None:
        def _get() -> RawIngestion | None:
            with self._session() as session:
                row = session.get(RawIngestion, run_id)
                if row is not None:
                    session.expunge(row)
                return row

        try:
            return await self._run(_get)
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(
                "Failed to fetch raw_ingestion row",
                details={"reason": str(exc)},
            ) from exc
