"""JSONPlaceholder posts source (strict Pydantic validation)."""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from core.config import Settings
from core.errors import PayloadValidationError
from db.models import IngestedItem, JsonPlaceholderPost
from services.http_fetch import auth_headers, fetch_json

_POSTS_ADAPTER = TypeAdapter(list[JsonPlaceholderPost])


async def fetch_posts(
    *,
    url: str,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> list[JsonPlaceholderPost]:
    """GET posts and validate the JSONPlaceholder shape."""
    payload = await fetch_json(url=url, timeout_seconds=timeout_seconds, headers=headers)
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


class JsonPlaceholderSource:
    """Default demo source: https://jsonplaceholder.typicode.com/posts."""

    name = "jsonplaceholder"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.origin = settings.source_url_str

    async def fetch(self) -> list[IngestedItem]:
        posts = await fetch_posts(
            url=self.origin,
            timeout_seconds=self._settings.http_timeout_seconds,
            headers=auth_headers(self._settings),
        )
        return [
            IngestedItem(
                id=str(post.id),
                body=post.body,
                payload=post.model_dump(by_alias=True),
            )
            for post in posts
        ]
