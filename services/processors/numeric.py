"""Numeric field processor: anomaly detection on a configured payload path.

Persistence mapping (no extra DB columns):
- ``word_count``: always ``0`` (text metric unused for numeric rows).
- ``average_word_count``: batch mean of the extracted numeric values (may be negative).
- ``is_anomaly``: same 1-population-stddev rule as word-count processing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from core.config import Settings
from core.errors import ConfigurationError, PayloadValidationError
from db.client import DatabaseClient
from db.models import IngestedItem, ProcessedMetricInsert, ProcessSummary
from services.processor import is_anomaly, mean, population_stddev
from services.sources.http_json import dig

logger = logging.getLogger(__name__)


def as_numeric(value: Any, *, path: str) -> float:
    """Require a JSON number that is int or float, not bool."""
    if isinstance(value, bool):
        raise PayloadValidationError(
            "Configured value field must be numeric",
            details={"path": path, "received_type": type(value).__name__},
        )
    if isinstance(value, int | float):
        return float(value)
    raise PayloadValidationError(
        "Configured value field must be numeric",
        details={"path": path, "received_type": type(value).__name__},
    )


def extract_numeric_value(record: IngestedItem, path: str) -> float:
    raw = dig(record.payload, path)
    return as_numeric(raw, path=path)


def build_metric_inserts(
    records: Sequence[IngestedItem],
    run_id: UUID,
    *,
    value_field: str,
) -> tuple[list[ProcessedMetricInsert], float, float]:
    values = [extract_numeric_value(record, value_field) for record in records]
    average = mean(values) if values else 0.0
    stddev = population_stddev(values, average)
    inserts = [
        ProcessedMetricInsert(
            run_id=run_id,
            post_id=record.id,
            word_count=0,
            average_word_count=average,
            is_anomaly=is_anomaly(value, average, stddev),
        )
        for record, value in zip(records, values, strict=True)
    ]
    return inserts, average, stddev


class NumericProcessor:
    """Score ``SOURCE_VALUE_FIELD`` from each record payload."""

    name = "numeric"

    def __init__(self, settings: Settings) -> None:
        field = settings.source_value_field.strip()
        if not field:
            raise ConfigurationError(
                "SOURCE_VALUE_FIELD must be set when PROCESSOR_NAME=numeric",
            )
        self._value_field = field

    async def process(
        self,
        db: DatabaseClient,
        records: Sequence[IngestedItem],
        run_id: UUID,
    ) -> ProcessSummary:
        inserts, average, stddev = build_metric_inserts(
            records,
            run_id,
            value_field=self._value_field,
        )
        persisted = await db.insert_processed_metrics(inserts)
        anomaly_count = sum(1 for record in persisted if record.is_anomaly)
        logger.info(
            "Processed (numeric) run_id=%s records=%s avg=%.3f stddev=%.3f anomalies=%s",
            run_id,
            len(persisted),
            average,
            stddev,
            anomaly_count,
        )
        return ProcessSummary(
            run_id=run_id,
            posts_processed=len(persisted),
            average_word_count=average,
            stddev=stddev,
            anomaly_count=anomaly_count,
            metrics=persisted,
        )


async def process_numeric(
    db: DatabaseClient,
    records: Sequence[IngestedItem],
    run_id: UUID,
    *,
    settings: Settings,
) -> ProcessSummary:
    """Module-level entry used by the registry factory."""
    processor = NumericProcessor(settings)
    return await processor.process(db, records, run_id)
