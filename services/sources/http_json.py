"""Generic HTTP JSON-array source with configurable id/text field paths."""

from __future__ import annotations

from typing import Any

from core.config import Settings
from core.errors import PayloadValidationError
from db.models import IngestedItem
from services.sources.pagination import fetch_all_record_rows


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


def as_item_id(value: Any, *, path: str) -> str:
    if isinstance(value, bool) or isinstance(value, float):
        raise PayloadValidationError(
            "Record id must be a non-empty string",
            details={"path": path, "received_type": type(value).__name__},
        )
    if isinstance(value, int):
        if value < 1:
            raise PayloadValidationError("Record id must be >= 1", details={"path": path})
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise PayloadValidationError(
                "Record id must be a non-empty string",
                details={"path": path},
            )
        if stripped.isdigit():
            parsed = int(stripped)
            if parsed < 1:
                raise PayloadValidationError("Record id must be >= 1", details={"path": path})
            return str(parsed)
        return stripped
    raise PayloadValidationError(
        "Record id must be a non-empty string",
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
        rows = await fetch_all_record_rows(self._settings)
        items: list[IngestedItem] = []
        seen_ids: set[str] = set()
        for row in rows:
            item_id = as_item_id(dig(row, self.id_field), path=self.id_field)
            if item_id in seen_ids:
                raise PayloadValidationError(
                    "Duplicate record id across paginated source",
                    details={"id": item_id},
                )
            seen_ids.add(item_id)
            body = as_text(dig(row, self.text_field), path=self.text_field)
            items.append(IngestedItem(id=item_id, body=body, payload=row))
        return items
