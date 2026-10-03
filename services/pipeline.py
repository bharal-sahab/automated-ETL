"""Fetch → process → persist orchestration with an overlap lock."""

from __future__ import annotations

import asyncio
import logging

from core.config import Settings
from core.errors import PipelineBusyError
from db.client import DatabaseClient
from db.models import MetricsListResponse, PipelineRunResponse
from services.ingestion import ingest_posts
from services.registry import get_processor, require_processor

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Single-flight pipeline used by the API and the background scheduler."""

    def __init__(self, db: DatabaseClient, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def run(self, *, skip_if_busy: bool = False) -> PipelineRunResponse:
        if skip_if_busy and self._lock.locked():
            logger.warning("Skipping pipeline run; previous run still in progress")
            raise PipelineBusyError()
        async with self._lock:
            return await self._run_unlocked()

    async def try_run(self) -> PipelineRunResponse | None:
        """Scheduler entrypoint: skip silently when a run is already active."""
        if self._lock.locked():
            logger.warning("Scheduler skipped overlapping pipeline run")
            return None
        async with self._lock:
            return await self._run_unlocked()

    async def list_metrics(self, *, limit: int, offset: int) -> MetricsListResponse:
        items, total = await self._db.fetch_processed_metrics(limit=limit, offset=offset)
        return MetricsListResponse(items=items, total=total, limit=limit, offset=offset)

    async def _run_unlocked(self) -> PipelineRunResponse:
        logger.info("Pipeline run starting")
        require_processor(self._settings)
        process = get_processor(self._settings)
        ingestion = await ingest_posts(self._db, self._settings)
        summary = await process(self._db, ingestion.posts, ingestion.record.id)
        result = PipelineRunResponse(
            run_id=ingestion.record.id,
            source=ingestion.record.source,
            posts_fetched=len(ingestion.posts),
            posts_processed=summary.posts_processed,
            average_word_count=summary.average_word_count,
            anomaly_count=summary.anomaly_count,
            fetched_at=ingestion.record.fetched_at,
        )
        logger.info(
            "Pipeline run finished run_id=%s processed=%s anomalies=%s",
            result.run_id,
            result.posts_processed,
            result.anomaly_count,
        )
        return result
