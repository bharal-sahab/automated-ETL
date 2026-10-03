"""SOURCE_ITEMS_PATH: unwrap a nested JSON array from an object root."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.config import Settings
from core.errors import PayloadValidationError
from services.sources.http_json import HttpJsonSource

CUSTOM_URL = "https://example.test/wrapped"


@pytest.fixture
def wrapped_list_settings() -> Settings:
    return Settings(
        source_name="http_json",
        source_url=CUSTOM_URL,
        source_items_path="data",
        source_id_field="id",
        source_text_field="body",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )


@respx.mock
@pytest.mark.asyncio
async def test_source_items_path_data_unwraps_nested_list(
    wrapped_list_settings: Settings,
) -> None:
    respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": 1, "body": "hello world"}]},
        )
    )
    source = HttpJsonSource(wrapped_list_settings)
    items = await source.fetch()
    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].body == "hello world"


@respx.mock
@pytest.mark.asyncio
async def test_source_items_path_missing_raises_payload_validation_error(
    wrapped_list_settings: Settings,
) -> None:
    respx.get(CUSTOM_URL).mock(return_value=httpx.Response(200, json={"other": []}))
    source = HttpJsonSource(wrapped_list_settings)
    with pytest.raises(PayloadValidationError):
        await source.fetch()


@respx.mock
@pytest.mark.asyncio
async def test_source_items_path_value_not_list_raises_payload_validation_error(
    wrapped_list_settings: Settings,
) -> None:
    respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(200, json={"data": {"id": 1, "body": "not a list"}})
    )
    source = HttpJsonSource(wrapped_list_settings)
    with pytest.raises(PayloadValidationError):
        await source.fetch()


@respx.mock
@pytest.mark.asyncio
async def test_blank_items_path_rejects_wrapper_object_root_must_be_list() -> None:
    settings = Settings(
        source_name="http_json",
        source_url=CUSTOM_URL,
        source_items_path="",
        source_id_field="id",
        source_text_field="body",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )
    respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": 1, "body": "hello world"}]},
        )
    )
    source = HttpJsonSource(settings)
    with pytest.raises(PayloadValidationError):
        await source.fetch()
