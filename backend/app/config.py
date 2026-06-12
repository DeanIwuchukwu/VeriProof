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
    # Sonnet is the accuracy/latency sweet spot. (Haiku was measured ~2x faster on simple
    # labels but repeatably garbles small back-label text — producer/importer names — and
    # was slower on hard labels, so it's not the default. The <5s target is met by the
    # no-proxy deploy environment; the raw image read is ~2.5s.) Swap via env.
    vision_model: str = Field(default="claude-sonnet-4-6", alias="TTB_VISION_MODEL")
    vision_max_tokens: int = Field(default=2048, alias="TTB_VISION_MAX_TOKENS")
    # Generous enough for the one-time structured-output schema compile + any TLS-proxy
    # overhead on the first call; warm calls are far quicker.
    request_timeout: float = Field(default=60.0, alias="TTB_REQUEST_TIMEOUT")
    # One retry on a transient blip, not the SDK default of 2 (avoids multiplying a slow call).
    max_retries: int = Field(default=1, alias="TTB_MAX_RETRIES")
    # Max records verified concurrently in a batch (balances throughput vs. provider rate limits).
    batch_concurrency: int = Field(default=5, alias="TTB_BATCH_CONCURRENCY")
    # Reject oversized batches outright (the peak-season case is ~200-300).
    batch_max_files: int = Field(default=400, alias="TTB_BATCH_MAX_FILES")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
