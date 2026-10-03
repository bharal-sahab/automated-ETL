"""Example source: read a local JSON array instead of calling HTTP.

Copy this module when a fork needs a source that is not ``http_json`` or
JSONPlaceholder. Register the class in ``services/registry.py``, then set
``SOURCE_NAME=file_json`` and ``SOURCE_FILE`` to a path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core.config import Settings
from core.errors import ConfigurationError, IngestionError, PayloadValidationError
from db.models import IngestedItem
from services.sources.http_json import as_item_id, as_text, dig


def _read_json_array(path: str) -> list[Any]:
    file_path = Path(path)
    try:
        raw = file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise IngestionError(
            "JSON file source path does not exist",
            details={"path": path},
        ) from exc
    except OSError as exc:
        raise IngestionError(
            "JSON file source could not be read",
            details={"path": path},
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PayloadValidationError(
            "JSON file source is not valid JSON",
            details={"path": path},
        ) from exc
    if not isinstance(payload, list):
        raise PayloadValidationError(
            "JSON file source must be a JSON array",
            details={"path": path, "received_type": type(payload).__name__},
        )
    return payload


class FileJsonSource:
    """Load ``[{id, body, ...}]`` from ``SOURCE_FILE`` (dotted field paths allowed)."""

    name = "file_json"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.origin = settings.source_file.strip()
        self.id_field = settings.source_id_field
        self.text_field = settings.source_text_field

    async def fetch(self) -> list[IngestedItem]:
        path = self._settings.source_file.strip()
        if not path:
            raise ConfigurationError(
                "SOURCE_FILE must be set when SOURCE_NAME=file_json",
            )
        self.origin = path
        rows = await asyncio.to_thread(_read_json_array, path)
        items: list[IngestedItem] = []
        seen_ids: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise PayloadValidationError(
                    "Each source row must be a JSON object",
                    details={"index": index, "received_type": type(row).__name__},
                )
            item_id = as_item_id(dig(row, self.id_field), path=self.id_field)
            if item_id in seen_ids:
                raise PayloadValidationError(
                    "Duplicate record id in JSON file source",
                    details={"id": item_id},
                )
            seen_ids.add(item_id)
            body = as_text(dig(row, self.text_field), path=self.text_field)
            items.append(IngestedItem(id=item_id, body=body, payload=row))
        return items
