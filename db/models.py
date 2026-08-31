"""SQLModel tables and Pydantic API/domain contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JsonPlaceholderPost(BaseModel):
    """A single post from JSONPlaceholder (`GET /posts`)."""

    model_config = ConfigDict(strict=True, populate_by_name=True, extra="forbid")

    user_id: int = Field(alias="userId", ge=0)
    id: int = Field(ge=1)
    title: str
    body: str


class RawIngestionInsert(BaseModel):
    """Validated payload for inserting a raw ingestion row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: str = Field(min_length=1)
    payload: list[dict[str, Any]]

    @field_validator("source")
    @classmethod
    def source_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must not be blank")
        return stripped


class ProcessedMetricInsert(BaseModel):
    """Validated payload for inserting a processed metric row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    run_id: UUID
    post_id: int | None = Field(default=None, ge=1)
    word_count: int = Field(ge=0)
    average_word_count: float = Field(ge=0)
    is_anomaly: bool = False


class RawIngestion(SQLModel, table=True):
    """Raw JSON payloads fetched from an upstream source."""

    __tablename__ = "raw_ingestion"
    __table_args__ = (Index("idx_raw_ingestion_fetched_at", "fetched_at"),)

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    source: str = SQLField(min_length=1, sa_column=Column(Text, nullable=False))
    payload: list[dict[str, Any]] = SQLField(sa_column=Column(JSON, nullable=False))
    fetched_at: datetime = SQLField(default_factory=utc_now, nullable=False, index=True)
    created_at: datetime = SQLField(default_factory=utc_now, nullable=False)

    @field_validator("source")
    @classmethod
    def source_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must not be blank")
        return stripped

    @field_validator("payload")
    @classmethod
    def payload_is_list(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError("payload must be a JSON array")
        return value


class ProcessedMetrics(SQLModel, table=True):
    """Per-post word counts and run-level average; anomaly uses 1-stddev from the run mean."""

    __tablename__ = "processed_metrics"
    __table_args__ = (
        Index("idx_processed_metrics_run_id", "run_id"),
        Index("idx_processed_metrics_processed_at", "processed_at"),
        Index("idx_processed_metrics_is_anomaly", "is_anomaly"),
    )

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    run_id: UUID = SQLField(foreign_key="raw_ingestion.id", nullable=False, index=True)
    post_id: int | None = SQLField(default=None, ge=1)
    word_count: int = SQLField(ge=0, nullable=False)
    average_word_count: float = SQLField(ge=0, nullable=False)
    is_anomaly: bool = SQLField(default=False, nullable=False)
    processed_at: datetime = SQLField(default_factory=utc_now, nullable=False, index=True)

    @field_validator("word_count")
    @classmethod
    def word_count_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("word_count must be >= 0")
        return value

    @field_validator("average_word_count")
    @classmethod
    def average_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("average_word_count must be >= 0")
        return value

    @field_validator("post_id")
    @classmethod
    def post_id_positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("post_id must be >= 1")
        return value


class PipelineRunResponse(BaseModel):
    run_id: UUID
    source: str
    posts_fetched: int = Field(ge=0)
    posts_processed: int = Field(ge=0)
    average_word_count: float
    anomaly_count: int = Field(ge=0)
    fetched_at: datetime
    skipped: bool = False


class MetricsListResponse(BaseModel):
    items: list[ProcessedMetrics]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str = "ok"
    scheduler_enabled: bool
    scheduler_running: bool


class ProcessSummary(BaseModel):
    run_id: UUID
    posts_processed: int
    average_word_count: float
    stddev: float
    anomaly_count: int
    metrics: list[ProcessedMetrics]


class IngestionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    record: RawIngestion
    posts: list[JsonPlaceholderPost]
