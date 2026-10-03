"""String record ids: normalization and validation at source boundaries."""

from __future__ import annotations

import httpx
import pytest
import respx
from core.config import Settings
from core.errors import PayloadValidationError
from services.sources.http_json import HttpJsonSource, as_item_id
from services.sources.jsonplaceholder import JsonPlaceholderSource

POSTS_URL = "https://jsonplaceholder.typicode.com/posts"
UUID_SAMPLE = "550e8400-e29b-41d4-a716-446655440000"


def test_integer_id_stored_as_string() -> None:
    assert as_item_id(7, path="id") == "7"


def test_uuid_string_id_preserved() -> None:
    assert as_item_id(UUID_SAMPLE, path="id") == UUID_SAMPLE


def test_blank_id_raises_payload_validation_error() -> None:
    with pytest.raises(PayloadValidationError, match="non-empty string"):
        as_item_id("   ", path="id")
    with pytest.raises(PayloadValidationError, match="non-empty string"):
        as_item_id("", path="event.id")


@respx.mock
@pytest.mark.asyncio
async def test_http_json_integer_id_normalized_to_string(settings: Settings) -> None:
    url = "https://example.test/records"
    custom = settings.model_copy(
        update={
            "source_name": "http_json",
            "source_url": url,
            "source_id_field": "id",
            "source_text_field": "body",
        }
    )
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 7, "body": "hello"}],
        )
    )
    items = await HttpJsonSource(custom).fetch()
    assert items[0].id == "7"


@respx.mock
@pytest.mark.asyncio
async def test_jsonplaceholder_stores_string_post_id(settings: Settings) -> None:
    respx.get(POSTS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "userId": 1,
                    "id": 42,
                    "title": "t",
                    "body": "body text",
                }
            ],
        )
    )
    items = await JsonPlaceholderSource(settings).fetch()
    assert len(items) == 1
    assert items[0].id == "42"
    assert isinstance(items[0].id, str)
    assert items[0].payload["id"] == 42

