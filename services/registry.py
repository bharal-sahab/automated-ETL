"""Register data sources and processors. Fork-friendly: add one line per plugin."""

from __future__ import annotations

from collections.abc import Callable

from core.config import Settings
from core.errors import ConfigurationError
from services.contracts import DataSource
from services.sources.http_json import HttpJsonSource
from services.sources.jsonplaceholder import JsonPlaceholderSource

SourceFactory = Callable[[Settings], DataSource]

SOURCE_FACTORIES: dict[str, SourceFactory] = {
    "jsonplaceholder": JsonPlaceholderSource,
    "http_json": HttpJsonSource,
}

PROCESSORS: tuple[str, ...] = ("word_count",)


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
