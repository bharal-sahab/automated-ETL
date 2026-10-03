"""Source HTTP auth header configuration and outbound requests."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.config import Settings
from services.http_fetch import auth_headers, fetch_json
from services.sources.http_json import HttpJsonSource
from services.sources.jsonplaceholder import fetch_posts

CUSTOM_URL = "https://example.test/secure-data"
POSTS_URL = "https://jsonplaceholder.typicode.com/posts"


def test_auth_headers_empty_token_returns_empty_dict(settings: Settings) -> None:
    assert settings.source_auth_token == ""
    assert auth_headers(settings) == {}


def test_auth_headers_bearer_secret_uses_exact_token_no_extra_prefix() -> None:
    settings = Settings(
        source_auth_header="Authorization",
        source_auth_token="Bearer secret",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )
    assert auth_headers(settings) == {"Authorization": "Bearer secret"}


@respx.mock
@pytest.mark.asyncio
async def test_fetch_json_sends_configured_auth_header() -> None:
    settings = Settings(
        source_auth_header="Authorization",
        source_auth_token="Bearer secret",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )
    route = respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(200, json=[{"id": 1, "body": "ok"}])
    )
    await fetch_json(
        url=CUSTOM_URL,
        timeout_seconds=5.0,
        headers=auth_headers(settings),
    )
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret"


@respx.mock
@pytest.mark.asyncio
async def test_http_json_fetch_sends_auth_header_when_token_set() -> None:
    settings = Settings(
        source_name="http_json",
        source_url=CUSTOM_URL,
        source_auth_header="Authorization",
        source_auth_token="Bearer secret",
        source_id_field="id",
        source_text_field="body",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )
    route = respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(200, json=[{"id": 1, "body": "hello"}])
    )
    source = HttpJsonSource(settings)
    items = await source.fetch()
    assert len(items) == 1
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret"


@respx.mock
@pytest.mark.asyncio
async def test_http_json_fetch_does_not_send_auth_when_token_blank() -> None:
    settings = Settings(
        source_name="http_json",
        source_url=CUSTOM_URL,
        source_auth_header="Authorization",
        source_auth_token="",
        source_id_field="id",
        source_text_field="body",
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )
    route = respx.get(CUSTOM_URL).mock(
        return_value=httpx.Response(200, json=[{"id": 1, "body": "hello"}])
    )
    source = HttpJsonSource(settings)
    await source.fetch()
    assert route.called
    request = route.calls.last.request
    assert "Authorization" not in request.headers


@respx.mock
@pytest.mark.asyncio
async def test_fetch_posts_works_without_headers_argument() -> None:
    respx.get(POSTS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "userId": 1,
                    "id": 1,
                    "title": "t",
                    "body": "one two three",
                }
            ],
        )
    )
    posts = await fetch_posts(url=POSTS_URL, timeout_seconds=5.0)
    assert len(posts) == 1
    assert posts[0].id == 1
