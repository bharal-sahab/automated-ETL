"""Generic HTTP JSON-array source with configurable id/text field paths."""

from __future__ import annotations

from typing import Any

from core.config import Settings
from core.errors import PayloadValidationError
from db.models import IngestedItem
from services.http_fetch import fetch_json


def dig(obj: dict[str, Any], path: str) -> Any:
    """Read a top-level or dotted path from a JSON object (`user.id`)."""
    current: Any = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise PayloadValidationError(
                "Record is missing a configured field path",
                details={"path": path, "missing": part},
            )
        current = current[part]
    return current


def as_item_id(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise PayloadValidationError(
            "Record id must be an integer",
            details={"path": path, "received_type": type(value).__name__},
        )
    if isinstance(value, int):
        if value < 1:
            raise PayloadValidationError("Record id must be >= 1", details={"path": path})
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if parsed < 1:
            raise PayloadValidationError("Record id must be >= 1", details={"path": path})
        return parsed
    raise PayloadValidationError(
        "Record id must be an integer",
        details={"path": path, "received_type": type(value).__name__},
    )


def as_text(value: Any, *, path: str) -> str:
    if value is None:
        raise PayloadValidationError("Record text must not be null", details={"path": path})
    if isinstance(value, str):
        return value
    return str(value)


class HttpJsonSource:
    """Any URL that returns a JSON array of objects.

    Map fields with SOURCE_ID_FIELD and SOURCE_TEXT_FIELD (dotted paths allowed).
    """

    name = "http_json"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.origin = settings.source_url_str
        self.id_field = settings.source_id_field
        self.text_field = settings.source_text_field

    async def fetch(self) -> list[IngestedItem]:
        payload = await fetch_json(
            url=self.origin,
            timeout_seconds=self._settings.http_timeout_seconds,
        )
        if not isinstance(payload, list):
            raise PayloadValidationError(
                "Source payload must be a JSON array",
                details={"received_type": type(payload).__name__},
            )
        items: list[IngestedItem] = []
        for index, row in enumerate(payload):
            if not isinstance(row, dict):
                raise PayloadValidationError(
                    "Each source row must be a JSON object",
                    details={"index": index, "received_type": type(row).__name__},
                )
            item_id = as_item_id(dig(row, self.id_field), path=self.id_field)
            body = as_text(dig(row, self.text_field), path=self.text_field)
            items.append(IngestedItem(id=item_id, body=body, payload=row))
        return items
