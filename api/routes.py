"""HTTP routes for health, manual pipeline trigger, and metrics."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from core.errors import PipelineBusyError
from db.models import HealthResponse, MetricsListResponse, PipelineRunResponse, RootResponse
from services.pipeline import PipelineOrchestrator
from services.registry import available_processors, available_sources

router = APIRouter()


def _orchestrator(request: Request) -> PipelineOrchestrator:
    return request.app.state.orchestrator


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    return RootResponse(
        name="automated-ETL",
        version="1.1.0",
        sources=available_sources(),
        processors=available_processors(),
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    scheduler = getattr(request.app.state, "scheduler", None)
    settings = getattr(request.app.state, "settings", None)
    enabled = bool(getattr(scheduler, "enabled", False))
    running = bool(getattr(scheduler, "running", False))
    source = getattr(settings, "source_name", None)
    processor = getattr(settings, "processor_name", None)
    return HealthResponse(
        status="ok",
        scheduler_enabled=enabled,
        scheduler_running=running,
        source=source,
        processor=processor,
    )


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(request: Request) -> PipelineRunResponse:
    orchestrator = _orchestrator(request)
    try:
        return await orchestrator.run(skip_if_busy=True)
    except PipelineBusyError:
        raise


@router.get("/metrics", response_model=MetricsListResponse)
async def list_metrics(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MetricsListResponse:
    return await _orchestrator(request).list_metrics(limit=limit, offset=offset)
