"""Ingestion service: success path and HTTP failures. HTTPX mocked; SQLite in-memory."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.config import Settings
from core.errors import IngestionError, PayloadValidationError
from db.client import DatabaseClient
from services.ingestion import fetch_posts, ingest_posts
from tests.conftest import SAMPLE_POSTS, pipeline_db_fingerprint

POSTS_URL = "https://jsonplaceholder.typicode.com/posts"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_success() -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    posts = await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)
    assert len(posts) == 3
    assert posts[0].user_id == 1
    assert posts[0].id == 1
    assert "three" in posts[0].body


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_http_error() -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(IngestionError) as exc_info:
        await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)
    assert exc_info.value.status_code == 502
    assert exc_info.value.details["status_code"] == 500


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_timeout() -> None:
    respx.get(POSTS_URL).mock(side_effect=httpx.TimeoutException("timeout"))
    with pytest.raises(IngestionError) as exc_info:
        await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)
    assert "Timed out" in exc_info.value.message


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_connection_error() -> None:
    respx.get(POSTS_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(IngestionError):
        await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_invalid_json() -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, text="not-json"))
    with pytest.raises(IngestionError) as exc_info:
        await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)
    assert "invalid JSON" in exc_info.value.message


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_non_array_payload() -> None:
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json={"posts": []}))
    with pytest.raises(PayloadValidationError):
        await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_ingest_posts_persists_raw_payload(db: DatabaseClient, settings: Settings) -> None:
    before = pipeline_db_fingerprint()
    respx.get(POSTS_URL).mock(return_value=httpx.Response(200, json=SAMPLE_POSTS))
    result = await ingest_posts(db, settings)
    assert len(result.posts) == 3
    stored = await db.get_raw_ingestion(result.record.id)
    assert stored is not None
    assert stored.source == POSTS_URL
    assert stored.payload[0]["userId"] == 1
    assert result.record.payload[0]["id"] == 1
    assert pipeline_db_fingerprint() == before
