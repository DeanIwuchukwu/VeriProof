"""Application configuration (env-driven; nothing secret is committed).

The vision provider/model are env-swappable — this is how the design answers the
firewall/on-prem concern (SPEC N5): change two env vars, not the code.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vision provider selection.
    #   "anthropic" — Claude vision (needs ANTHROPIC_API_KEY)
    #   "fake"      — deterministic stub for offline dev / tests (no network)
    vision_provider: str = Field(default="anthropic", alias="TTB_VISION_PROVIDER")
    # Default to a FAST vision model: the <5s latency target (the constraint that
    # killed the prior vendor) outweighs maximal capability. Swap via env.
    vision_model: str = Field(default="claude-sonnet-4-6", alias="TTB_VISION_MODEL")
    vision_max_tokens: int = Field(default=2048, alias="TTB_VISION_MAX_TOKENS")
    request_timeout: float = Field(default=30.0, alias="TTB_REQUEST_TIMEOUT")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
