"""Fetch JSONPlaceholder posts and persist the raw payload."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from core.config import Settings
from core.errors import IngestionError, PayloadValidationError
from db.client import DatabaseClient
from db.models import IngestionResult, JsonPlaceholderPost, RawIngestionInsert

logger = logging.getLogger(__name__)

_POSTS_ADAPTER = TypeAdapter(list[JsonPlaceholderPost])


async def fetch_posts(
    *,
    url: str,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> list[JsonPlaceholderPost]:
    """GET posts from the mock API and validate with Pydantic."""

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        try:
            response = await http_client.get(url)
        except httpx.TimeoutException as exc:
            raise IngestionError(
                "Timed out fetching posts",
                details={"url": url, "timeout_seconds": timeout_seconds},
            ) from exc
        except httpx.RequestError as exc:
            raise IngestionError(
                "Failed to reach posts API",
                details={"url": url, "reason": str(exc)},
            ) from exc

        if response.status_code >= 400:
            raise IngestionError(
                "Posts API returned an error status",
                details={"url": url, "status_code": response.status_code},
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise IngestionError(
                "Posts API returned invalid JSON",
                details={"url": url},
            ) from exc

        if not isinstance(payload, list):
            raise PayloadValidationError(
                "Posts API payload must be a JSON array",
                details={"received_type": type(payload).__name__},
            )

        try:
            return _POSTS_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise PayloadValidationError(
                "Posts API payload failed validation",
                details={"errors": exc.errors()},
            ) from exc
    finally:
        if owns_client:
            await http_client.aclose()


async def ingest_posts(db: DatabaseClient, settings: Settings) -> IngestionResult:
    """Fetch posts, validate, persist raw_ingestion, return posts + record."""

    url = settings.mock_api_url_str
    logger.info("Fetching posts from %s", url)
    posts = await fetch_posts(url=url, timeout_seconds=settings.http_timeout_seconds)
    insert = RawIngestionInsert(
        source=url,
        payload=[post.model_dump(by_alias=True) for post in posts],
    )
    record = await db.insert_raw_ingestion(insert)
    logger.info("Stored raw ingestion run_id=%s posts=%s", record.id, len(posts))
    return IngestionResult(record=record, posts=posts)
