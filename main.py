"""FastAPI application factory and lifespan (settings, DB, scheduler)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from core.config import Settings, get_settings
from core.errors import register_exception_handlers
from core.scheduler import PipelineScheduler
from db.client import DatabaseClient
from services.pipeline import PipelineOrchestrator

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = getattr(app.state, "settings", None) or get_settings()
    db: DatabaseClient = getattr(app.state, "db", None) or DatabaseClient(settings)
    if not db.is_connected:
        await db.connect()

    orchestrator: PipelineOrchestrator = (
        getattr(app.state, "orchestrator", None) or PipelineOrchestrator(db, settings)
    )
    scheduler: PipelineScheduler = getattr(app.state, "scheduler", None) or PipelineScheduler(
        orchestrator,
        interval_seconds=float(settings.ingestion_interval_seconds),
        enabled=settings.scheduler_enabled,
    )

    app.state.settings = settings
    app.state.db = db
    app.state.orchestrator = orchestrator
    app.state.scheduler = scheduler

    await scheduler.start()
    logger.info("Application startup complete")
    try:
        yield
    finally:
        await scheduler.stop()
        await db.close()
        logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(
        title="Ingestion Pipeline",
        description="JSONPlaceholder → SQLite raw ingest + word-count metrics",
        version="1.0.0",
        lifespan=lifespan,
    )
    register_exception_handlers(application)
    application.include_router(router)
    return application


app = create_app()
