"""Plugin contracts for data sources and processors."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from db.models import IngestedItem, ProcessedMetricInsert, ProcessSummary


class RecordLike(Protocol):
    """Anything a word-count processor can score."""

    id: int
    body: str


@runtime_checkable
class DataSource(Protocol):
    """Fetch records from an upstream system and normalize them."""

    name: str
    origin: str

    async def fetch(self) -> list[IngestedItem]: ...


class Processor(Protocol):
    name: str

    def build_metric_inserts(
        self,
        records: list[RecordLike],
        run_id: UUID,
    ) -> tuple[list[ProcessedMetricInsert], float, float]: ...

    async def process(self, records: list[RecordLike], run_id: UUID) -> ProcessSummary: ...
