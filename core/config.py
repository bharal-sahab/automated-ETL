"""Application settings loaded from environment / .env."""

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ingestion pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="sqlite:///./pipeline.db",
        description="SQLAlchemy URL. Default is a local pipeline.db file. Tests use sqlite:///:memory:.",
    )
    ingestion_interval_seconds: int = Field(default=300, ge=1)
    mock_api_url: HttpUrl = Field(default="https://jsonplaceholder.typicode.com/posts")
    scheduler_enabled: bool = Field(default=True)
    http_timeout_seconds: float = Field(default=30.0, gt=0)

    @property
    def mock_api_url_str(self) -> str:
        return str(self.mock_api_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
