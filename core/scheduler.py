"""Background asyncio scheduler for the ingestion pipeline."""

from __future__ import annotations

import asyncio
import logging

from core.errors import AppError
from services.pipeline import PipelineOrchestrator

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Runs the pipeline on a fixed interval without overlapping executions."""

    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        *,
        interval_seconds: float,
        enabled: bool = True,
    ) -> None:
        self._orchestrator = orchestrator
        self._interval_seconds = interval_seconds
        self._enabled = enabled
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def start(self) -> None:
        if not self._enabled:
            logger.info("Scheduler disabled; not starting")
            return
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="ingestion-scheduler")
        logger.info("Scheduler started interval_seconds=%s", self._interval_seconds)

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        while not self._stop.is_set():
            await self._run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                continue

    async def _run_once(self) -> None:
        logger.info("Scheduled pipeline run starting")
        try:
            result = await self._orchestrator.try_run()
            if result is None:
                logger.warning("Scheduled pipeline run skipped (overlap guard)")
                return
            logger.info("Scheduled pipeline run finished run_id=%s", result.run_id)
        except asyncio.CancelledError:
            raise
        except AppError:
            logger.exception("Scheduled pipeline run failed with application error")
        except Exception:
            logger.exception("Scheduled pipeline run failed")
