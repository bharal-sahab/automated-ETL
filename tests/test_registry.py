"""Plugin registry: known sources, custom registration, unknown names."""

from __future__ import annotations

import pytest

from core.config import Settings
from core.errors import ConfigurationError
from db.models import IngestedItem
from services.registry import (
    available_processors,
    available_sources,
    get_source,
    register_source,
    require_processor,
)


def test_default_plugins_are_registered() -> None:
    assert "jsonplaceholder" in available_sources()
    assert "http_json" in available_sources()
    assert "file_json" in available_sources()
    assert available_processors() == ["word_count", "numeric"]


def test_unknown_source_raises(settings: Settings) -> None:
    bad = settings.model_copy(update={"source_name": "not-a-source"})
    with pytest.raises(ConfigurationError, match="Unknown SOURCE_NAME"):
        get_source(bad)


def test_unknown_processor_raises(settings: Settings) -> None:
    bad = settings.model_copy(update={"processor_name": "magic"})
    with pytest.raises(ConfigurationError, match="Unknown PROCESSOR_NAME"):
        require_processor(bad)


@pytest.mark.asyncio
async def test_register_source_is_used(settings: Settings) -> None:
    class FakeSource:
        name = "fake"
        origin = "memory://fake"

        def __init__(self, _settings: Settings) -> None:
            pass

        async def fetch(self) -> list[IngestedItem]:
            return [IngestedItem(id="1", body="hello", payload={"id": 1, "body": "hello"})]

    register_source("fake", FakeSource)
    try:
        source = get_source(settings.model_copy(update={"source_name": "fake"}))
        items = await source.fetch()
        assert items[0].body == "hello"
        assert "fake" in available_sources()
    finally:
        from services import registry

        registry.SOURCE_FACTORIES.pop("fake", None)
