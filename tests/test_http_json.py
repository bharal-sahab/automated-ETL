"""Generic http_json source: any JSON array, mapped id/text fields."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.config import Settings
from core.errors import PayloadValidationError
from db.client import DatabaseClient
from services.ingestion import ingest_posts
from services.sources.http_json import HttpJsonSource, dig

CUSTOM_URL = "https://example.test/events"


@pytest.fixture
def http_json_settings() -> Settings:
    return Settings(
        source_name="http_json",
        source_url=CUSTOM_URL,
        source_id_field="event.id",
        source_text_field="message",
        scheduler_enabled=False,
        database_url="sqlite:///:memory:",
    )


@respx.mock
@pytest.mark.asyncio
async def test_http_json_maps_dotted_fields(http_json_settings: Settings) -> None:
    respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"event": {"id": 10}, "message": "alpha beta"},
                {"event": {"id": "11"}, "message": "gamma"},
            ],
        )
    )
    source = HttpJsonSource(http_json_settings)
    items = await source.fetch()
    assert [item.id for item in items] == ["10", "11"]
    assert items[0].body == "alpha beta"
    assert items[0].payload["event"]["id"] == 10


@respx.mock
@pytest.mark.asyncio
async def test_http_json_ingest_persists(
    db: DatabaseClient, http_json_settings: Settings
) -> None:
    respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(
            200,
            json=[{"event": {"id": 1}, "message": "hello world"}],
        )
    )
    result = await ingest_posts(db, http_json_settings)
    assert len(result.posts) == 1
    assert result.posts[0].id == "1"
    assert result.record.source == CUSTOM_URL
    stored = await db.get_raw_ingestion(result.record.id)
    assert stored is not None
    assert stored.payload[0]["message"] == "hello world"


@respx.mock
@pytest.mark.asyncio
async def test_http_json_missing_field_raises(http_json_settings: Settings) -> None:
    respx.get(CUSTOM_URL).mock(return_value=httpx.Response(200, json=[{"message": "no id"}]))
    source = HttpJsonSource(http_json_settings)
    with pytest.raises(PayloadValidationError):
        await source.fetch()


def test_dig_nested_object() -> None:
    assert dig({"a": {"b": 3}}, "a.b") == 3
