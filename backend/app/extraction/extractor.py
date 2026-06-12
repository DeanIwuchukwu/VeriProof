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
        result = self._provider.extract(images)
        # Net contents is the field most often missed on hard layouts (e.g. the small
        # checkbox list on a circular keg collar). On a first-pass miss, spend ONE focused
        # re-read to recover it before the engine reports it as not found.
        if not (result.net_contents.present and result.net_contents.value):
            retry = self._provider.extract_net_contents(images)
            if retry.present and retry.value:
                result.net_contents = retry
        return result
