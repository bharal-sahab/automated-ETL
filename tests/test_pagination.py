"""SOURCE_NEXT_FIELD, SOURCE_PAGE_PARAM, and SOURCE_MAX_PAGES pagination."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.config import Settings
from core.errors import ConfigurationError, IngestionError, PayloadValidationError
from services.sources.http_json import HttpJsonSource

BASE_URL = "https://example.test/api/items"
PAGE2_URL = "https://example.test/api/items/page-2"


def _base_settings(**overrides: object) -> Settings:
    return Settings(
        source_name="http_json",
        source_url=BASE_URL,
        source_id_field="id",
        source_text_field="body",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
        **overrides,
    )


@respx.mock
@pytest.mark.asyncio
async def test_blank_pagination_settings_single_get_returns_items() -> None:
    settings = _base_settings(
        source_items_path="",
        source_next_field="",
        source_page_param="",
    )
    route = respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "body": "one"},
                {"id": 2, "body": "two"},
            ],
        )
    )
    items = await HttpJsonSource(settings).fetch()
    assert route.call_count == 1
    assert [item.id for item in items] == ["1", "2"]


@respx.mock
@pytest.mark.asyncio
async def test_next_field_walks_pages_until_next_missing() -> None:
    settings = _base_settings(
        source_items_path="data",
        source_next_field="links.next",
    )
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 1, "body": "a"}],
                "links": {"next": PAGE2_URL},
            },
        )
    )
    respx.get(PAGE2_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 2, "body": "b"}],
                "links": {},
            },
        )
    )
    items = await HttpJsonSource(settings).fetch()
    assert [item.id for item in items] == ["1", "2"]
    assert respx.calls.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_page_param_increments_until_empty_page() -> None:
    settings = _base_settings(
        source_items_path="results",
        source_page_param="page",
    )
    respx.get(url__regex=r"https://example\.test/api/items\?page=1").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"id": 1, "body": "p1"}]},
        )
    )
    respx.get(url__regex=r"https://example\.test/api/items\?page=2").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"id": 2, "body": "p2"}]},
        )
    )
    respx.get(url__regex=r"https://example\.test/api/items\?page=3").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    items = await HttpJsonSource(settings).fetch()
    assert [item.id for item in items] == ["1", "2"]
    assert respx.calls.call_count == 3


@pytest.mark.asyncio
async def test_both_pagination_modes_raises_configuration_error_no_http() -> None:
    settings = _base_settings(
        source_items_path="data",
        source_next_field="links.next",
        source_page_param="page",
    )
    with respx.mock:
        with pytest.raises(ConfigurationError, match="cannot both be set"):
            await HttpJsonSource(settings).fetch()
        assert respx.calls.call_count == 0


@pytest.mark.asyncio
async def test_next_field_without_items_path_raises_configuration_error() -> None:
    settings = _base_settings(
        source_items_path="",
        source_next_field="links.next",
    )
    with respx.mock:
        with pytest.raises(ConfigurationError, match="SOURCE_ITEMS_PATH"):
            await HttpJsonSource(settings).fetch()
        assert respx.calls.call_count == 0


@respx.mock
@pytest.mark.asyncio
async def test_duplicate_id_across_pages_raises_payload_validation_error() -> None:
    settings = _base_settings(
        source_items_path="data",
        source_next_field="links.next",
    )
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 1, "body": "first"}],
                "links": {"next": PAGE2_URL},
            },
        )
    )
    respx.get(PAGE2_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 1, "body": "dup"}],
                "links": {},
            },
        )
    )
    with pytest.raises(PayloadValidationError, match="Duplicate record id"):
        await HttpJsonSource(settings).fetch()


@respx.mock
@pytest.mark.asyncio
async def test_auth_header_sent_on_second_paginated_request() -> None:
    settings = _base_settings(
        source_items_path="data",
        source_next_field="links.next",
        source_auth_header="Authorization",
        source_auth_token="Bearer secret",
    )
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 1, "body": "a"}],
                "links": {"next": PAGE2_URL},
            },
        )
    )
    page2_route = respx.get(PAGE2_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 2, "body": "b"}],
                "links": {},
            },
        )
    )
    await HttpJsonSource(settings).fetch()
    assert page2_route.called
    assert page2_route.calls.last.request.headers["Authorization"] == "Bearer secret"


@respx.mock
@pytest.mark.asyncio
async def test_source_max_pages_one_with_next_link_raises_ingestion_error() -> None:
    settings = _base_settings(
        source_items_path="data",
        source_next_field="links.next",
        source_max_pages=1,
    )
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": 1, "body": "only"}],
                "links": {"next": PAGE2_URL},
            },
        )
    )
    page2_route = respx.get(PAGE2_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": 2, "body": "never"}]},
        )
    )
    with pytest.raises(IngestionError, match="maximum number of source pages"):
        await HttpJsonSource(settings).fetch()
    assert page2_route.call_count == 0
