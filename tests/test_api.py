"""API: health, pipeline trigger, metrics. In-memory SQLite; HTTP mocked."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from core.config import Settings
from core.errors import PipelineBusyError
from core.scheduler import PipelineScheduler
from db.client import DatabaseClient
from main import create_app
from services.pipeline import PipelineOrchestrator
from tests.conftest import SAMPLE_POSTS, pipeline_db_fingerprint

POSTS_URL = "https://jsonplaceholder.typicode.com/posts"


@pytest.fixture
def app(settings: Settings):
    application = create_app()
    application.state.settings = settings
    return application


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scheduler_enabled"] is False
    assert body["scheduler_running"] is False
    assert body["source"] == "jsonplaceholder"
    assert body["processor"] == "word_count"


def test_root_lists_plugins(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "automated-ETL"
    assert body["version"] == "1.2.0"
    assert "jsonplaceholder" in body["sources"]
    assert "http_json" in body["sources"]
    assert "file_json" in body["sources"]
    assert "word_count" in body["processors"]
    assert body["docs"] == "/docs"


@respx.mock
def test_pipeline_run(client: TestClient) -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    response = client.post("/pipeline/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["posts_fetched"] == 3
    assert body["posts_processed"] == 3
    assert "run_id" in body
    assert body["anomaly_count"] >= 0


@respx.mock
def test_pipeline_run_upstream_failure(client: TestClient) -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(503, json={"error": "down"}))
    response = client.post("/pipeline/run")
    assert response.status_code == 502
    assert "error" in response.json()


def test_get_metrics_empty(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 50
    assert body["offset"] == 0


@respx.mock
def test_get_metrics_with_pagination(client: TestClient) -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    run = client.post("/pipeline/run")
    assert run.status_code == 200, run.text
    response = client.get("/metrics", params={"limit": 2, "offset": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2
    assert {item["post_id"] for item in body["items"]} <= {"1", "2", "3"}


def test_metrics_rejects_bad_limit(client: TestClient) -> None:
    response = client.get("/metrics", params={"limit": 0})
    assert response.status_code == 422


def test_pipeline_busy_returns_409(app) -> None:
    with TestClient(app) as client:
        orchestrator: PipelineOrchestrator = app.state.orchestrator
        original_run = orchestrator.run

        async def busy_run(*, skip_if_busy: bool = False) -> None:
            raise PipelineBusyError()

        orchestrator.run = busy_run  # type: ignore[method-assign]
        try:
            response = client.post("/pipeline/run")
            assert response.status_code == 409
            assert "already in progress" in response.json()["error"]
        finally:
            orchestrator.run = original_run  # type: ignore[method-assign]


@respx.mock
def test_api_does_not_create_pipeline_db(client: TestClient) -> None:
    before = pipeline_db_fingerprint()
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    response = client.post("/pipeline/run")
    assert response.status_code == 200
    assert pipeline_db_fingerprint() == before


def test_lifespan_uses_in_memory_client(client: TestClient, app) -> None:
    db: DatabaseClient = app.state.db
    assert db.is_connected is True
    assert ":memory:" in db.database_url
    scheduler: PipelineScheduler = app.state.scheduler
    assert scheduler.enabled is False
