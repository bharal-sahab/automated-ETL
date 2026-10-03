"""Shared fixtures: env, in-memory SQLite, sample posts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from core.config import Settings, clear_settings_cache
from db.client import DatabaseClient

SAMPLE_POSTS: list[dict[str, Any]] = [
    {"userId": 1, "id": 1, "title": "alpha", "body": "one two three"},
    {"userId": 1, "id": 2, "title": "beta", "body": "one two three four five six seven eight nine ten eleven twelve"},
    {"userId": 2, "id": 3, "title": "gamma", "body": "short"},
]


@pytest.fixture(autouse=True)
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("INGESTION_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("SOURCE_NAME", "jsonplaceholder")
    monkeypatch.setenv("PROCESSOR_NAME", "word_count")
    monkeypatch.setenv("SOURCE_URL", "https://jsonplaceholder.typicode.com/posts")
    monkeypatch.setenv("MOCK_API_URL", "https://jsonplaceholder.typicode.com/posts")
    monkeypatch.setenv("SOURCE_ID_FIELD", "id")
    monkeypatch.setenv("SOURCE_TEXT_FIELD", "body")
    monkeypatch.setenv("SOURCE_ITEMS_PATH", "")
    monkeypatch.setenv("SOURCE_VALUE_FIELD", "")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("SOURCE_AUTH_HEADER", "Authorization")
    monkeypatch.setenv("SOURCE_AUTH_TOKEN", "")
    monkeypatch.setenv("SOURCE_ITEMS_PATH", "")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def settings(test_env: None) -> Settings:
    return Settings()


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def run_id():
    return uuid4()


@pytest.fixture
async def db(settings: Settings) -> AsyncIterator[DatabaseClient]:
    """Temporary in-memory SQLite. Does not touch pipeline.db."""
    client = DatabaseClient(settings)
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


def pipeline_db_fingerprint() -> tuple[bool, int | None]:
    """(exists, mtime_ns) for the on-disk pipeline.db next to the repo root."""
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "pipeline.db"
    if not path.exists():
        return False, None
    return True, path.stat().st_mtime_ns
