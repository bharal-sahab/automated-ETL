"""file_json example source: local JSON array, no HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.config import Settings
from core.errors import ConfigurationError, IngestionError, PayloadValidationError
from db.client import DatabaseClient
from services.pipeline import PipelineOrchestrator
from services.registry import get_source
from services.sources.file_json import FileJsonSource

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "records.json"


def _settings(path: str) -> Settings:
    return Settings(
        source_name="file_json",
        source_file=path,
        database_url="sqlite:///:memory:",
        scheduler_enabled=False,
    )


@pytest.mark.asyncio
async def test_example_file_returns_text_ids() -> None:
    items = await FileJsonSource(_settings(str(EXAMPLE))).fetch()
    assert [item.id for item in items] == ["alpha", "beta"]
    assert items[0].body == "one two three"
    assert get_source(_settings(str(EXAMPLE))).name == "file_json"


@pytest.mark.asyncio
async def test_dotted_id_field(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps([{"event": {"id": 7}, "message": "hello world"}]),
        encoding="utf-8",
    )
    settings = _settings(str(path)).model_copy(
        update={"source_id_field": "event.id", "source_text_field": "message"}
    )
    items = await FileJsonSource(settings).fetch()
    assert items[0].id == "7"
    assert items[0].body == "hello world"


@pytest.mark.asyncio
async def test_blank_source_file_raises_configuration_error(tmp_path: Path) -> None:
    missing = tmp_path / "never-read.json"
    with pytest.raises(ConfigurationError, match="SOURCE_FILE"):
        await FileJsonSource(_settings("")).fetch()
    assert not missing.exists()


@pytest.mark.asyncio
async def test_missing_file_raises_ingestion_error(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="does not exist"):
        await FileJsonSource(_settings(str(tmp_path / "missing.json"))).fetch()


@pytest.mark.asyncio
async def test_object_root_raises_payload_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "wrapped.json"
    path.write_text(json.dumps({"data": []}), encoding="utf-8")
    with pytest.raises(PayloadValidationError, match="JSON array"):
        await FileJsonSource(_settings(str(path))).fetch()


@pytest.mark.asyncio
async def test_duplicate_id_raises_payload_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "dupes.json"
    path.write_text(
        json.dumps(
            [
                {"id": "same", "body": "a"},
                {"id": "same", "body": "b"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(PayloadValidationError, match="Duplicate record id"):
        await FileJsonSource(_settings(str(path))).fetch()


@pytest.mark.asyncio
async def test_pipeline_scores_file_without_http(db: DatabaseClient) -> None:
    settings = _settings(str(EXAMPLE))
    result = await PipelineOrchestrator(db, settings).run()
    assert result.posts_fetched == 2
    assert result.posts_processed == 2
    rows, total = await db.fetch_processed_metrics(limit=10, offset=0)
    assert total == 2
    assert {row.post_id for row in rows} == {"alpha", "beta"}
