"""Application configuration (env-driven; nothing secret is committed)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vision provider selection.
    #   "openai"    - GPT vision (needs OPENAI_API_KEY)
    #   "anthropic" - Claude vision (needs ANTHROPIC_API_KEY)
    #   "fake"      - deterministic stub for offline dev / tests (no network)
    vision_provider: str = Field(default="openai", alias="TTB_VISION_PROVIDER")
    # Favor the lighter GPT-5.4 mini model to better fit the PRD's sub-5s target.
    vision_model: str = Field(default="gpt-5.4-mini", alias="TTB_VISION_MODEL")
    vision_max_tokens: int = Field(default=2048, alias="TTB_VISION_MAX_TOKENS")
    request_timeout: float = Field(default=60.0, alias="TTB_REQUEST_TIMEOUT")
    max_retries: int = Field(default=1, alias="TTB_MAX_RETRIES")
    batch_concurrency: int = Field(default=5, alias="TTB_BATCH_CONCURRENCY")
    batch_max_files: int = Field(default=400, alias="TTB_BATCH_MAX_FILES")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # Persistence. Railway injects DATABASE_URL; locally it lives in backend/.env.
    # When unset the app still runs — verifications are just not saved (see app/db.py).
    database_url: str | None = Field(default=None, alias="DATABASE_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
