"""Application configuration using pydantic settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration for the redaction service."""

    model_config = SettingsConfigDict(env_prefix="MCP_", case_sensitive=False)

    max_payload_bytes: int = Field(1_048_576, ge=1_024, le=8_388_608)
    rate_limit_requests: int = Field(120, ge=1)
    rate_limit_window_seconds: int = Field(60, ge=1)
    request_timeout_seconds: int = Field(15, ge=1)
    mapping_ttl_seconds: Optional[int] = Field(86_400, ge=60)
    cleanup_interval_seconds: int = Field(300, ge=30)
    deterministic_secret: str = Field(..., min_length=32)
    redis_url: Optional[str] = None
    redis_ssl: bool = False
    log_directory: Path = Field(default=Path("docs/logs"))
    chat_directory: Path = Field(default=Path("docs/chat"))
    environment: str = Field("production")

    @property
    def deterministic_secret_bytes(self) -> bytes:
        return self.deterministic_secret.encode("utf-8")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached settings instance."""

    settings = AppSettings()
    # Ensure required directories exist eagerly to avoid race conditions later.
    settings.log_directory.mkdir(parents=True, exist_ok=True)
    settings.chat_directory.mkdir(parents=True, exist_ok=True)
    return settings
