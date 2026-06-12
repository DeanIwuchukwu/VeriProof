"""Anthropic vision provider for label extraction."""

from __future__ import annotations

import base64

import anthropic

from app.cola.models import LabelImage
from app.extraction.common import (
    EXTRACTION_INSTRUCTIONS,
    SYSTEM_PROMPT,
    clamp_confidences,
    parse_json_object,
)
from app.extraction.provider import VisionProvider
from app.extraction.schema import ExtractedLabel
from app.extraction.tls import use_system_trust_store

_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

class AnthropicVisionProvider(VisionProvider):
    def __init__(
        self, api_key: str | None, model: str, max_tokens: int, timeout: float, max_retries: int = 1
    ):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it, or run with TTB_VISION_PROVIDER=fake for offline mode."
            )
        use_system_trust_store()
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self._model = model
        self._max_tokens = max_tokens

    def extract(self, images: list[LabelImage]) -> ExtractedLabel:
        if not images:
            return ExtractedLabel(image_quality="low", notes="No label images provided.")

        content: list[dict] = []
        for idx, img in enumerate(images):
            label = img.image_type or "label"
            content.append({"type": "text", "text": f"Image index {idx} ({label}):"})
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _MEDIA_TYPES.get(img.image_format.lower(), "image/jpeg"),
                        "data": base64.standard_b64encode(img.data).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": EXTRACTION_INSTRUCTIONS})

        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        data = parse_json_object(text)
        return clamp_confidences(ExtractedLabel.model_validate(data))
