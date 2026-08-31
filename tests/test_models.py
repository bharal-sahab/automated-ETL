"""Pydantic validation of JSONPlaceholder posts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from db.models import JsonPlaceholderPost, ProcessedMetrics, RawIngestion


def test_valid_post() -> None:
    post = JsonPlaceholderPost.model_validate(
        {"userId": 1, "id": 10, "title": "hello", "body": "world"}
    )
    assert post.user_id == 1
    assert post.id == 10
    dumped = post.model_dump(by_alias=True)
    assert dumped["userId"] == 1
    assert "user_id" not in dumped


def test_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        JsonPlaceholderPost.model_validate({"userId": 1, "id": 1, "title": "x"})


def test_wrong_types() -> None:
    with pytest.raises(ValidationError):
        JsonPlaceholderPost.model_validate(
            {"userId": "1", "id": 1, "title": "x", "body": "y"}
        )
    with pytest.raises(ValidationError):
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 1, "title": "x", "body": 123}
        )


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 1, "title": "x", "body": "y", "extra": True}
        )


def test_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 0, "title": "x", "body": "y"}
        )


def test_raw_ingestion_requires_source_and_payload() -> None:
    row = RawIngestion.model_validate(
        {"source": "https://example.test/posts", "payload": [{"id": 1}]}
    )
    assert row.source == "https://example.test/posts"
    assert row.payload == [{"id": 1}]
    assert row.id is not None
    with pytest.raises(ValidationError):
        RawIngestion.model_validate({"source": "", "payload": []})


def test_processed_metrics_rejects_negative_word_count() -> None:
    with pytest.raises(ValidationError):
        ProcessedMetrics.model_validate(
            {
                "run_id": RawIngestion.model_validate({"source": "x", "payload": []}).id,
                "post_id": 1,
                "word_count": -1,
                "average_word_count": 0.0,
            }
        )


def test_table_names() -> None:
    assert RawIngestion.__tablename__ == "raw_ingestion"
    assert ProcessedMetrics.__tablename__ == "processed_metrics"
