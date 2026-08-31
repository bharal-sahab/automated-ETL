"""HTTP routes for health, manual pipeline trigger, and metrics."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from core.errors import PipelineBusyError
from db.models import HealthResponse, MetricsListResponse, PipelineRunResponse
from services.pipeline import PipelineOrchestrator

router = APIRouter()


def _orchestrator(request: Request) -> PipelineOrchestrator:
    return request.app.state.orchestrator


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    scheduler = getattr(request.app.state, "scheduler", None)
    enabled = bool(getattr(scheduler, "enabled", False))
    running = bool(getattr(scheduler, "running", False))
    return HealthResponse(status="ok", scheduler_enabled=enabled, scheduler_running=running)


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
