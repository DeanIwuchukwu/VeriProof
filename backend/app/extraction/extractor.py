"""Extractor — orchestrates vision extraction over a label image set.

Thin today (delegates to the configured VisionProvider); the seam exists so image
preprocessing (downscale/deskew for latency) or multi-call aggregation can be added
without touching callers.
"""

from __future__ import annotations

from app.cola.models import LabelImage
from app.extraction.provider import VisionProvider, get_vision_provider
from app.extraction.schema import ExtractedLabel


class Extractor:
    def __init__(self, provider: VisionProvider | None = None):
        self._provider = provider or get_vision_provider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def extract(self, images: list[LabelImage]) -> ExtractedLabel:
        return self._provider.extract(images)
