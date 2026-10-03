"""Multi-page HTTP JSON fetch for :class:`HttpJsonSource`."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from core.config import Settings
from core.errors import ConfigurationError, IngestionError, PayloadValidationError
from services.http_fetch import auth_headers, fetch_json


def _validate_pagination_config(settings: Settings) -> None:
    next_field = settings.source_next_field.strip()
    page_param = settings.source_page_param.strip()
    if next_field and page_param:
        raise ConfigurationError(
            "SOURCE_NEXT_FIELD and SOURCE_PAGE_PARAM cannot both be set",
            details={"source_next_field": next_field, "source_page_param": page_param},
        )
    if next_field and not settings.source_items_path.strip():
        raise ConfigurationError(
            "SOURCE_ITEMS_PATH must be set when SOURCE_NEXT_FIELD is set",
            details={"source_next_field": next_field},
        )


def extract_record_rows(payload: Any, settings: Settings) -> list[dict[str, Any]]:
    """Pull the list of record objects from one page payload."""
    from services.sources.http_json import dig

    items_path = settings.source_items_path.strip()
    if items_path:
        if not isinstance(payload, dict):
            raise PayloadValidationError(
                "Source payload must be a JSON object when SOURCE_ITEMS_PATH is set",
                details={"received_type": type(payload).__name__, "path": items_path},
            )
        try:
            records = dig(payload, items_path)
        except PayloadValidationError as exc:
            raise PayloadValidationError(
                "Source payload is missing configured items path",
                details={"path": items_path, **(exc.details or {})},
            ) from exc
        if not isinstance(records, list):
            raise PayloadValidationError(
                "Configured items path must resolve to a JSON array",
                details={"path": items_path, "received_type": type(records).__name__},
            )
        rows = records
    elif not isinstance(payload, list):
        raise PayloadValidationError(
            "Source payload must be a JSON array",
            details={"received_type": type(payload).__name__},
        )
    else:
        rows = payload

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PayloadValidationError(
                "Each source row must be a JSON object",
                details={"index": index, "received_type": type(row).__name__},
            )
    return rows


def _read_next_link(payload: dict[str, Any], path: str) -> str | None:
    from services.sources.http_json import dig

    try:
        value = dig(payload, path)
    except PayloadValidationError:
        return None
    if value is None:
        return None
    if not isinstance(value, str):
        raise PayloadValidationError(
            "Pagination next link must be a string",
            details={"path": path, "received_type": type(value).__name__},
        )
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _url_with_page_param(url: str, param: str, page: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query[param] = [str(page)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


async def _fetch_single_page(settings: Settings, headers: dict[str, str]) -> list[dict[str, Any]]:
    payload = await fetch_json(
        url=settings.source_url_str,
        timeout_seconds=settings.http_timeout_seconds,
        headers=headers,
    )
    return extract_record_rows(payload, settings)


async def _fetch_via_next_link(
    settings: Settings,
    headers: dict[str, str],
    next_field: str,
) -> list[dict[str, Any]]:
    max_pages = settings.source_max_pages
    url = settings.source_url_str
    fetched_urls: set[str] = set()
    all_rows: list[dict[str, Any]] = []
    pages_fetched = 0

    while True:
        if pages_fetched >= max_pages:
            raise IngestionError(
                "Exceeded configured maximum number of source pages",
                details={"source_max_pages": max_pages},
            )
        if url in fetched_urls:
            raise IngestionError(
                "Pagination next link repeated a previously fetched URL",
                details={"url": url},
            )

        payload = await fetch_json(
            url=url,
            timeout_seconds=settings.http_timeout_seconds,
            headers=headers,
        )
        pages_fetched += 1
        fetched_urls.add(url)

        if not isinstance(payload, dict):
            raise PayloadValidationError(
                "Source payload must be a JSON object when SOURCE_NEXT_FIELD is set",
                details={"received_type": type(payload).__name__},
            )

        all_rows.extend(extract_record_rows(payload, settings))

        next_url = _read_next_link(payload, next_field)
        if next_url is None:
            break
        url = next_url

    return all_rows


async def _fetch_via_page_param(
    settings: Settings,
    headers: dict[str, str],
    page_param: str,
) -> list[dict[str, Any]]:
    max_pages = settings.source_max_pages
    all_rows: list[dict[str, Any]] = []
    page = 1
    pages_fetched = 0

    while True:
        if pages_fetched >= max_pages:
            raise IngestionError(
                "Exceeded configured maximum number of source pages",
                details={"source_max_pages": max_pages},
            )

        url = _url_with_page_param(settings.source_url_str, page_param, page)
        payload = await fetch_json(
            url=url,
            timeout_seconds=settings.http_timeout_seconds,
            headers=headers,
        )
        pages_fetched += 1

        rows = extract_record_rows(payload, settings)
        if not rows:
            break
        all_rows.extend(rows)
        page += 1

    return all_rows


async def fetch_all_record_rows(settings: Settings) -> list[dict[str, Any]]:
    """Fetch and concatenate record rows from one or more JSON pages."""
    _validate_pagination_config(settings)
    headers = auth_headers(settings)

    next_field = settings.source_next_field.strip()
    page_param = settings.source_page_param.strip()

    if not next_field and not page_param:
        return await _fetch_single_page(settings, headers)
    if next_field:
        return await _fetch_via_next_link(settings, headers, next_field)
    return await _fetch_via_page_param(settings, headers, page_param)
