"""Shared async HTTP JSON fetch used by all HTTP data sources."""

from __future__ import annotations

from typing import Any

import httpx

from core.errors import IngestionError


async def fetch_json(
    *,
    url: str,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """GET a URL and parse JSON. Raises IngestionError on transport/HTTP/JSON failures."""

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        try:
            response = await http_client.get(url)
        except httpx.TimeoutException as exc:
            raise IngestionError(
                "Timed out fetching source",
                details={"url": url, "timeout_seconds": timeout_seconds},
            ) from exc
        except httpx.RequestError as exc:
            raise IngestionError(
                "Failed to reach source API",
                details={"url": url, "reason": str(exc)},
            ) from exc

        if response.status_code >= 400:
            raise IngestionError(
                "Source API returned an error status",
                details={"url": url, "status_code": response.status_code},
            )

        try:
            return response.json()
        except ValueError as exc:
            raise IngestionError(
                "Source API returned invalid JSON",
                details={"url": url},
            ) from exc
    finally:
        if owns_client:
            await http_client.aclose()
