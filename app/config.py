"""Application settings, loaded from environment variables / a local .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    request_timeout_seconds: float = 15.0   # per HTTP request
    platform_timeout_seconds: float = 30.0  # wall-clock budget per platform
    verify_public_access: bool = True

    devto_api_key: SecretStr | None = None
    telegraph_access_token: SecretStr | None = None
    bluesky_identifier: str | None = None
    bluesky_app_password: SecretStr | None = None
    github_token: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_channel_username: str | None = None


def reveal(value: SecretStr | str | None) -> str | None:
    """Return the plain string for a secret/str setting, or None if unset/blank."""
    if value is None:
        return None
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    raw = raw.strip()
    return raw or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
