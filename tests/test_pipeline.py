"""Pipeline orchestration and overlap guard. In-memory SQLite; HTTPX mocked."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from core.config import Settings
from core.errors import PipelineBusyError
from db.client import DatabaseClient
from services.pipeline import PipelineOrchestrator
from tests.conftest import SAMPLE_POSTS

POSTS_URL = "https://jsonplaceholder.typicode.com/posts"


@respx.mock
@pytest.mark.asyncio
async def test_pipeline_run_fetches_processes_persists(
    db: DatabaseClient, settings: Settings
) -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    orchestrator = PipelineOrchestrator(db, settings)
    result = await orchestrator.run()
    assert result.posts_fetched == 3
    assert result.posts_processed == 3
    assert result.anomaly_count >= 0
    assert result.source == POSTS_URL
    items, total = await db.fetch_processed_metrics(limit=10, offset=0)
    assert total == 3
    assert {row.post_id for row in items} == {1, 2, 3}


@pytest.mark.asyncio
async def test_try_run_skips_when_lock_held(db: DatabaseClient, settings: Settings) -> None:
    orchestrator = PipelineOrchestrator(db, settings)
    await orchestrator._lock.acquire()
    try:
        result = await orchestrator.try_run()
        assert result is None
    finally:
        orchestrator._lock.release()
    items, total = await db.fetch_processed_metrics(limit=10, offset=0)
    assert total == 0
    assert items == []


@pytest.mark.asyncio
async def test_run_skip_if_busy_raises(db: DatabaseClient, settings: Settings) -> None:
    orchestrator = PipelineOrchestrator(db, settings)
    await orchestrator._lock.acquire()
    try:
        with pytest.raises(PipelineBusyError):
            await orchestrator.run(skip_if_busy=True)
    finally:
        orchestrator._lock.release()


@pytest.mark.asyncio
async def test_overlap_guard_during_in_flight_run(
    db: DatabaseClient, settings: Settings
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    original = db.insert_raw_ingestion

    async def gated(data):
        started.set()
        await release.wait()
        return await original(data)

    db.insert_raw_ingestion = gated  # type: ignore[method-assign]
    orchestrator = PipelineOrchestrator(db, settings)

    async def first_run() -> None:
        with respx.mock:
            respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
            await orchestrator.run()

    task = asyncio.create_task(first_run())
    await started.wait()
    skipped = await orchestrator.try_run()
    assert skipped is None
    release.set()
    await task
