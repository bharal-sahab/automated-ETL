"""DatabaseClient against in-memory SQLite (does not touch pipeline.db)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.config import Settings
from core.errors import DatabaseError
from db.client import DatabaseClient, is_memory_url, normalize_database_url
from db.models import ProcessedMetricInsert, RawIngestionInsert


@pytest.mark.asyncio
async def test_insert_raw_ingestion_roundtrip(db: DatabaseClient) -> None:
    record = await db.insert_raw_ingestion(
        RawIngestionInsert(
            source="https://jsonplaceholder.typicode.com/posts",
            payload=[{"userId": 1, "id": 1, "title": "t", "body": "b"}],
        )
    )
    loaded = await db.get_raw_ingestion(record.id)
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.source.endswith("/posts")
    assert loaded.payload[0]["id"] == 1


@pytest.mark.asyncio
async def test_not_connected_raises(settings: Settings) -> None:
    client = DatabaseClient(settings)
    with pytest.raises(DatabaseError, match="not connected"):
        await client.insert_raw_ingestion(RawIngestionInsert(source="x", payload=[]))


@pytest.mark.asyncio
async def test_insert_processed_metrics(db: DatabaseClient) -> None:
    raw = await db.insert_raw_ingestion(RawIngestionInsert(source="https://example.test", payload=[]))
    rows = await db.insert_processed_metrics(
        [
            ProcessedMetricInsert(
                run_id=raw.id,
                post_id=1,
                word_count=3,
                average_word_count=3.0,
                is_anomaly=False,
            )
        ]
    )
    assert len(rows) == 1
    assert rows[0].post_id == 1
    by_run = await db.fetch_processed_metrics_by_run(raw.id)
    assert len(by_run) == 1
    assert by_run[0].word_count == 3


@pytest.mark.asyncio
async def test_insert_processed_metrics_empty(db: DatabaseClient) -> None:
    assert await db.insert_processed_metrics([]) == []


@pytest.mark.asyncio
async def test_insert_metrics_without_parent_raises(db: DatabaseClient) -> None:
    with pytest.raises(DatabaseError):
        await db.insert_processed_metrics(
            [
                ProcessedMetricInsert(
                    run_id=uuid4(),
                    post_id=1,
                    word_count=1,
                    average_word_count=1.0,
                    is_anomaly=False,
                )
            ]
        )


@pytest.mark.asyncio
async def test_fetch_processed_metrics_pagination(db: DatabaseClient) -> None:
    raw = await db.insert_raw_ingestion(RawIngestionInsert(source="https://example.test", payload=[]))
    inserts = [
        ProcessedMetricInsert(
            run_id=raw.id,
            post_id=i,
            word_count=i,
            average_word_count=2.0,
            is_anomaly=False,
        )
        for i in range(1, 4)
    ]
    await db.insert_processed_metrics(inserts)
    page, total = await db.fetch_processed_metrics(limit=2, offset=1)
    assert total == 3
    assert len(page) == 2


@pytest.mark.asyncio
async def test_fetch_rejects_bad_paging(db: DatabaseClient) -> None:
    with pytest.raises(DatabaseError, match="limit"):
        await db.fetch_processed_metrics(limit=0, offset=0)
    with pytest.raises(DatabaseError, match="offset"):
        await db.fetch_processed_metrics(limit=10, offset=-1)


@pytest.mark.asyncio
async def test_connect_creates_schema_and_closes(settings: Settings) -> None:
    client = DatabaseClient(settings)
    assert client.is_connected is False
    await client.connect()
    assert client.is_connected is True
    await client.connect()  # idempotent
    assert is_memory_url(client.database_url)
    await client.close()
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_connect_creates_pipeline_db_file(tmp_path: Path) -> None:
    db_file = tmp_path / "pipeline.db"
    settings = Settings(database_url=f"sqlite:///{db_file}")
    client = DatabaseClient(settings)
    await client.connect()
    try:
        assert db_file.exists()
        await client.insert_raw_ingestion(RawIngestionInsert(source="file-test", payload=[]))
    finally:
        await client.close()


def test_normalize_memory_url() -> None:
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert normalize_database_url("sqlite+aiosqlite:///:memory:") == "sqlite:///:memory:"
    assert is_memory_url("sqlite:///:memory:") is True


def test_insert_dto_rejects_blank_source() -> None:
    with pytest.raises(ValidationError):
        RawIngestionInsert(source="   ", payload=[])


def test_metric_insert_rejects_negative_word_count() -> None:
    with pytest.raises(ValidationError):
        ProcessedMetricInsert(
            run_id=uuid4(),
            post_id=1,
            word_count=-1,
            average_word_count=0.0,
            is_anomaly=False,
        )
