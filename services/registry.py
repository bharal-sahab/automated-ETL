"""Register data sources and processors. Fork-friendly: add one line per plugin."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from core.config import Settings
from core.errors import ConfigurationError
from db.client import DatabaseClient
from db.models import IngestedItem, ProcessSummary
from services.contracts import DataSource
from services.processor import process_posts as process_word_count
from services.processors.numeric import NumericProcessor
from services.sources.file_json import FileJsonSource
from services.sources.http_json import HttpJsonSource
from services.sources.jsonplaceholder import JsonPlaceholderSource

SourceFactory = Callable[[Settings], DataSource]

ProcessorRunner = Callable[
    [DatabaseClient, Sequence[IngestedItem], UUID],
    Awaitable[ProcessSummary],
]

SOURCE_FACTORIES: dict[str, SourceFactory] = {
    "jsonplaceholder": JsonPlaceholderSource,
    "http_json": HttpJsonSource,
    "file_json": FileJsonSource,
}

PROCESSORS: tuple[str, ...] = ("word_count", "numeric")


def register_source(name: str, factory: SourceFactory) -> None:
    """Call from a custom module (or tests) to add a source without a core edit."""
    key = name.strip().lower()
    if not key:
        raise ConfigurationError("Source name must not be blank")
    SOURCE_FACTORIES[key] = factory


def available_sources() -> list[str]:
    return sorted(SOURCE_FACTORIES)


def available_processors() -> list[str]:
    return list(PROCESSORS)


def get_source(settings: Settings) -> DataSource:
    key = settings.source_name.strip().lower()
    factory = SOURCE_FACTORIES.get(key)
    if factory is None:
        raise ConfigurationError(
            f"Unknown SOURCE_NAME '{settings.source_name}'",
            details={"available": available_sources()},
        )
    return factory(settings)


def require_processor(settings: Settings) -> str:
    key = settings.processor_name.strip().lower()
    if key not in PROCESSORS:
        raise ConfigurationError(
            f"Unknown PROCESSOR_NAME '{settings.processor_name}'",
            details={"available": available_processors()},
        )
    return key


def get_processor(settings: Settings) -> ProcessorRunner:
    """Return an async runner ``(db, records, run_id) -> ProcessSummary``."""
    key = require_processor(settings)
    if key == "word_count":
        return process_word_count
    if key == "numeric":
        processor = NumericProcessor(settings)

        async def run_numeric(
            db: DatabaseClient,
            records: Sequence[IngestedItem],
            run_id: UUID,
        ) -> ProcessSummary:
            return await processor.process(db, records, run_id)

        return run_numeric
    raise ConfigurationError(
        f"Unknown PROCESSOR_NAME '{settings.processor_name}'",
        details={"available": available_processors()},
    )
