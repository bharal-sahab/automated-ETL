"""Word-count processing and anomaly detection for a batch of posts."""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from uuid import UUID

from db.client import DatabaseClient
from db.models import ProcessedMetricInsert, ProcessSummary
from services.contracts import RecordLike

logger = logging.getLogger(__name__)

# Anomaly rule: flag a post when |word_count - mean| > 1 * population stddev.
# If the batch has < 2 posts or stddev == 0 (all counts equal), no anomalies.
ANOMALY_STDDEV_MULTIPLIER = 1.0


def count_words(text: str) -> int:
    """Count whitespace-delimited words in a post body."""
    return len(text.split())


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def population_stddev(values: list[float], average: float) -> float:
    """Population standard deviation; 0.0 when n < 2."""
    n = len(values)
    if n < 2:
        return 0.0
    variance = sum((value - average) ** 2 for value in values) / n
    return math.sqrt(variance)


def is_anomaly(word_count: int, average: float, stddev: float) -> bool:
    """True when word_count is more than one stddev from the run mean."""
    if stddev <= 0:
        return False
    return abs(word_count - average) > (ANOMALY_STDDEV_MULTIPLIER * stddev)


def build_metric_inserts(
    posts: Sequence[RecordLike],
    run_id: UUID,
) -> tuple[list[ProcessedMetricInsert], float, float]:
    """Compute word counts, run average, stddev, and anomaly flags."""
    counts = [count_words(post.body) for post in posts]
    average = mean([float(count) for count in counts]) if counts else 0.0
    stddev = population_stddev([float(count) for count in counts], average)
    inserts = [
        ProcessedMetricInsert(
            run_id=run_id,
            post_id=post.id,
            word_count=word_count,
            average_word_count=average,
            is_anomaly=is_anomaly(word_count, average, stddev),
        )
        for post, word_count in zip(posts, counts, strict=True)
    ]
    return inserts, average, stddev


async def process_posts(
    db: DatabaseClient,
    posts: Sequence[RecordLike],
    run_id: UUID,
) -> ProcessSummary:
    """Score posts and persist processed_metrics rows."""
    inserts, average, stddev = build_metric_inserts(posts, run_id)
    records = await db.insert_processed_metrics(inserts)
    anomaly_count = sum(1 for record in records if record.is_anomaly)
    logger.info(
        "Processed run_id=%s posts=%s avg=%.3f stddev=%.3f anomalies=%s",
        run_id,
        len(records),
        average,
        stddev,
        anomaly_count,
    )
    return ProcessSummary(
        run_id=run_id,
        posts_processed=len(records),
        average_word_count=average,
        stddev=stddev,
        anomaly_count=anomaly_count,
        metrics=records,
    )
