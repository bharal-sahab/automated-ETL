"""Numeric processor: SOURCE_VALUE_FIELD, anomalies, and configuration."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from core.errors import ConfigurationError, PayloadValidationError
from db.client import DatabaseClient
from db.models import IngestedItem, RawIngestionInsert
from main import create_app
from services.processors.numeric import NumericProcessor, build_metric_inserts
from services.registry import get_processor, require_processor

VALUE_PATH = "metrics.value"


def _numeric_item(post_id: str, value: float | bool) -> IngestedItem:
    return IngestedItem(
        id=post_id,
        body="ignored for numeric",
        payload={"id": post_id, "metrics": {"value": value}},
    )


def test_numeric_outlier_flagged_only_for_extreme_value() -> None:
    records = [
        _numeric_item("1", 10.0),
        _numeric_item("2", 10.0),
        _numeric_item("3", 10.0),
        _numeric_item("99", 100.0),
    ]
    inserts, average, stddev = build_metric_inserts(
        records, uuid4(), value_field=VALUE_PATH
    )
    assert average == 32.5
    assert stddev > 0
    assert all(row.word_count == 0 for row in inserts)
    assert all(row.average_word_count == average for row in inserts)
    assert [row.post_id for row in inserts] == ["1", "2", "3", "99"]
    assert all(isinstance(row.post_id, str) for row in inserts)
    flags = {row.post_id: row.is_anomaly for row in inserts}
    assert flags == {"1": False, "2": False, "3": False, "99": True}


def test_numeric_equal_values_produce_no_anomalies() -> None:
    records = [_numeric_item(str(i), 5.0) for i in range(1, 4)]
    inserts, _average, stddev = build_metric_inserts(
        records, uuid4(), value_field=VALUE_PATH
    )
    assert stddev == 0.0
    assert all(row.is_anomaly is False for row in inserts)
    assert all(row.word_count == 0 for row in inserts)


def test_numeric_missing_value_path_raises() -> None:
    record = IngestedItem(id="1", body="", payload={"id": "1"})
    with pytest.raises(PayloadValidationError, match="missing"):
        build_metric_inserts([record], uuid4(), value_field=VALUE_PATH)


def test_numeric_bool_value_raises_payload_validation_error() -> None:
    record = _numeric_item("1", True)
    with pytest.raises(PayloadValidationError, match="numeric"):
        build_metric_inserts([record], uuid4(), value_field=VALUE_PATH)


def test_blank_source_value_field_raises_configuration_error(settings: Settings) -> None:
    numeric_settings = settings.model_copy(
        update={"processor_name": "numeric", "source_value_field": "   "}
    )
    with pytest.raises(ConfigurationError, match="SOURCE_VALUE_FIELD"):
        NumericProcessor(numeric_settings)


def test_unknown_processor_name_raises_configuration_error(settings: Settings) -> None:
    bad = settings.model_copy(update={"processor_name": "not-real"})
    with pytest.raises(ConfigurationError, match="Unknown PROCESSOR_NAME"):
        require_processor(bad)
    with pytest.raises(ConfigurationError, match="Unknown PROCESSOR_NAME"):
        get_processor(bad)


def test_unknown_processor_api_returns_400(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setenv("PROCESSOR_NAME", "not-real")
    from core.config import clear_settings_cache

    clear_settings_cache()
    app = create_app()
    app.state.settings = settings.model_copy(update={"processor_name": "not-real"})
    with TestClient(app) as client:
        response = client.post("/pipeline/run")
    assert response.status_code == 400
    assert "Unknown PROCESSOR_NAME" in response.json()["error"]


@pytest.mark.asyncio
async def test_numeric_processor_persists_metrics(
    db: DatabaseClient, settings: Settings
) -> None:
    numeric_settings = settings.model_copy(
        update={"processor_name": "numeric", "source_value_field": VALUE_PATH}
    )
    processor = NumericProcessor(numeric_settings)
    raw = await db.insert_raw_ingestion(
        RawIngestionInsert(source="test://numeric", payload=[{"id": "10"}])
    )
    run_id = raw.id
    records = [
        _numeric_item("10", 1.0),
        _numeric_item("20", 1.0),
        _numeric_item("30", 1.0),
        _numeric_item("40", 20.0),
    ]
    summary = await processor.process(db, records, run_id)
    assert summary.posts_processed == 4
    assert summary.anomaly_count == 1
    stored, total = await db.fetch_processed_metrics(limit=10, offset=0)
    assert total == 4
    assert all(row.word_count == 0 for row in stored)
    assert {row.post_id for row in stored if row.is_anomaly} == {"40"}
