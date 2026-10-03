"""Fetch from the configured data source and persist the raw payload."""

from __future__ import annotations

import logging

from core.config import Settings
from db.client import DatabaseClient
from db.models import IngestionResult, RawIngestionInsert
from services.registry import get_source
from services.sources.jsonplaceholder import fetch_posts

logger = logging.getLogger(__name__)

__all__ = ["fetch_posts", "ingest_posts"]


async def ingest_posts(db: DatabaseClient, settings: Settings) -> IngestionResult:
    """Fetch via the registered source, persist raw_ingestion, return items + record."""

    source = get_source(settings)
    logger.info("Fetching from source=%s origin=%s", source.name, source.origin)
    items = await source.fetch()
    insert = RawIngestionInsert(
        source=source.origin,
        payload=[item.payload for item in items],
    )
    record = await db.insert_raw_ingestion(insert)
    logger.info("Stored raw ingestion run_id=%s items=%s", record.id, len(items))
    return IngestionResult(record=record, posts=items)
