"""Scheduler start/stop and overlap skip."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from core.scheduler import PipelineScheduler
from db.models import PipelineRunResponse
from services.pipeline import PipelineOrchestrator


@pytest.mark.asyncio
async def test_scheduler_disabled_does_not_start() -> None:
    orchestrator = AsyncMock(spec=PipelineOrchestrator)
    scheduler = PipelineScheduler(orchestrator, interval_seconds=0.05, enabled=False)
    await scheduler.start()
    assert scheduler.running is False
    orchestrator.try_run.assert_not_called()
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_run_once_skips_when_try_run_returns_none() -> None:
    orchestrator = AsyncMock(spec=PipelineOrchestrator)
    orchestrator.try_run = AsyncMock(return_value=None)
    scheduler = PipelineScheduler(orchestrator, interval_seconds=60, enabled=True)
    await scheduler._run_once()
    orchestrator.try_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_run_once_logs_success() -> None:
    orchestrator = AsyncMock(spec=PipelineOrchestrator)
    from datetime import datetime, timezone
    from uuid import uuid4

    orchestrator.try_run = AsyncMock(
        return_value=PipelineRunResponse(
            run_id=uuid4(),
            source="https://jsonplaceholder.typicode.com/posts",
            posts_fetched=1,
            posts_processed=1,
            average_word_count=2.0,
            anomaly_count=0,
            fetched_at=datetime.now(timezone.utc),
        )
    )
    scheduler = PipelineScheduler(orchestrator, interval_seconds=60, enabled=True)
    await scheduler._run_once()
    orchestrator.try_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_loop() -> None:
    orchestrator = AsyncMock(spec=PipelineOrchestrator)
    orchestrator.try_run = AsyncMock(return_value=None)
    scheduler = PipelineScheduler(orchestrator, interval_seconds=0.05, enabled=True)
    await scheduler.start()
    assert scheduler.running is True
    await scheduler.stop()
    assert scheduler.running is False
    await asyncio.sleep(0)
