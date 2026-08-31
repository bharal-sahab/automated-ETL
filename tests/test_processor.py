"""Processor: word counts, averages, and anomaly flagging."""

from __future__ import annotations

from uuid import uuid4

from db.models import JsonPlaceholderPost
from services.processor import (
    build_metric_inserts,
    count_words,
    is_anomaly,
    mean,
    population_stddev,
)


def test_count_words_splits_on_whitespace() -> None:
    assert count_words("hello world") == 2
    assert count_words("  leading and trailing  ") == 3
    assert count_words("") == 0
    assert count_words("one") == 1


def test_mean_and_stddev_empty_and_single() -> None:
    assert mean([]) == 0.0
    assert population_stddev([], 0.0) == 0.0
    assert population_stddev([4.0], 4.0) == 0.0


def test_is_anomaly_false_when_stddev_zero() -> None:
    assert is_anomaly(100, 100.0, 0.0) is False
    assert is_anomaly(1, 5.0, 0.0) is False


def test_anomaly_flagging_one_stddev() -> None:
    posts = [
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 1, "title": "a", "body": "one"}
        ),
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 2, "title": "b", "body": "one"}
        ),
        JsonPlaceholderPost.model_validate(
            {"userId": 1, "id": 3, "title": "c", "body": "one"}
        ),
        JsonPlaceholderPost.model_validate(
            {
                "userId": 1,
                "id": 4,
                "title": "d",
                "body": "one two three four five six seven eight nine ten",
            }
        ),
    ]
    inserts, average, stddev = build_metric_inserts(posts, uuid4())
    assert average == 13 / 4
    assert stddev > 0
    flags = [row.is_anomaly for row in inserts]
    assert flags[:3] == [False, False, False]
    assert flags[3] is True
    assert all(row.average_word_count == average for row in inserts)


def test_no_anomalies_when_all_counts_equal() -> None:
    posts = [
        JsonPlaceholderPost.model_validate({"userId": 1, "id": i, "title": "t", "body": "one two"})
        for i in range(1, 4)
    ]
    inserts, _average, stddev = build_metric_inserts(posts, uuid4())
    assert stddev == 0.0
    assert all(row.is_anomaly is False for row in inserts)
    assert all(row.word_count == 2 for row in inserts)


def test_single_post_is_not_an_anomaly() -> None:
    posts = [
        JsonPlaceholderPost.model_validate({"userId": 1, "id": 1, "title": "t", "body": "only one post body here"})
    ]
    inserts, average, stddev = build_metric_inserts(posts, uuid4())
    assert stddev == 0.0
    assert inserts[0].is_anomaly is False
    assert inserts[0].word_count == 5
    assert inserts[0].average_word_count == average
