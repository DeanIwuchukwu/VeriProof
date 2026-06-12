"""VisionProvider interface + factory.

The interface is the seam that makes the AI swappable (SPEC N5). Concrete providers:
Anthropic (default), a deterministic Fake (offline dev / tests). A local-OCR provider
could be added here without touching the matching engine or the API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.cola.models import LabelImage
from app.config import Settings, get_settings
from app.extraction.schema import ExtractedField, ExtractedLabel


class VisionProvider(ABC):
    """Reads label image(s) into a structured :class:`ExtractedLabel`."""

    @abstractmethod
    def extract(self, images: list[LabelImage]) -> ExtractedLabel: ...

    @property
    def name(self) -> str:
        return type(self).__name__


class FakeVisionProvider(VisionProvider):
    """Deterministic stub so the app and its tests run without network or a key.

    Returns a fixed, fully-compliant reading. Useful for wiring tests and local
    demos; never used when a real key is configured.
    """

    def extract(self, images: list[LabelImage]) -> ExtractedLabel:
        from app.matching.warning_text import CANONICAL_WARNING

        def f(value: str | None) -> ExtractedField:
            return ExtractedField(value=value, present=value is not None, confidence=0.9, source_image=0)

        return ExtractedLabel(
            brand_name=f("OLD TOM DISTILLERY"),
            fanciful_name=f(None),
            class_type=f("Kentucky Straight Bourbon Whiskey"),
            alcohol_content=f("45% Alc./Vol. (90 Proof)"),
            net_contents=f("750 mL"),
            producer_name=f("Old Tom Distillery"),
            producer_address=f("Louisville, KY"),
            country_of_origin=f(None),
            government_warning=f(CANONICAL_WARNING),
            warning_prefix_all_caps=True,
            warning_appears_bold=True,
            image_quality="good",
            overall_confidence=0.9,
            notes="fake provider (no model call)",
        )


def get_vision_provider(settings: Settings | None = None) -> VisionProvider:
    settings = settings or get_settings()
    provider = settings.vision_provider.lower()
    if provider == "fake":
        return FakeVisionProvider()
    if provider == "anthropic":
        # Imported lazily so the package doesn't hard-require the SDK/key for `fake`.
        from app.extraction.anthropic_provider import AnthropicVisionProvider

        return AnthropicVisionProvider(
            api_key=settings.anthropic_api_key,
            model=settings.vision_model,
            max_tokens=settings.vision_max_tokens,
            timeout=settings.request_timeout,
        )
    raise ValueError(f"Unknown vision provider: {settings.vision_provider!r}")
