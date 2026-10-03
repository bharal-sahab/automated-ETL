"""Application settings loaded from environment / .env."""

from functools import lru_cache

from pydantic import AliasChoices, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ingestion pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    database_url: str = Field(
        default="sqlite:///./pipeline.db",
        description="SQLAlchemy URL. Default is a local pipeline.db file. Tests use sqlite:///:memory:.",
    )
    ingestion_interval_seconds: int = Field(default=300, ge=1)
    source_name: str = Field(
        default="jsonplaceholder",
        description="Registered data source: jsonplaceholder or http_json.",
    )
    processor_name: str = Field(
        default="word_count",
        description="Registered processor. Built-in: word_count, numeric.",
    )
    source_value_field: str = Field(
        default="",
        description=(
            "Object key (dotted path ok) for the numeric value when PROCESSOR_NAME=numeric."
        ),
    )
    source_url: HttpUrl = Field(
        default="https://jsonplaceholder.typicode.com/posts",
        validation_alias=AliasChoices("SOURCE_URL", "MOCK_API_URL", "source_url"),
        description="HTTP JSON endpoint. MOCK_API_URL is accepted as a legacy alias.",
    )
    source_id_field: str = Field(
        default="id",
        min_length=1,
        description="Object key (dotted path ok) used as the record id for SOURCE_NAME=http_json.",
    )
    source_text_field: str = Field(
        default="body",
        min_length=1,
        description="Object key (dotted path ok) used as text for SOURCE_NAME=http_json.",
    )
    source_items_path: str = Field(
        default="",
        description=(
            "Dotted path on the JSON root object to the array of records "
            "(SOURCE_NAME=http_json). Empty means the root must be an array."
        ),
    )
    source_auth_header: str = Field(
        default="Authorization",
        min_length=1,
        description="HTTP header name for SOURCE_AUTH_TOKEN when set.",
    )
    source_auth_token: str = Field(
        default="",
        description="Value for SOURCE_AUTH_HEADER. Empty means no auth header is sent.",
    )
    scheduler_enabled: bool = Field(default=True)
    http_timeout_seconds: float = Field(default=30.0, gt=0)

    @property
    def source_url_str(self) -> str:
        return str(self.source_url)

    @property
    def mock_api_url_str(self) -> str:
        """Backward-compatible alias for source_url_str."""
        return self.source_url_str


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
