"""OpenAI vision provider for label extraction."""

from __future__ import annotations

import base64

from openai import OpenAI

from app.cola.models import LabelImage
from app.extraction.common import (
    EXTRACTION_INSTRUCTIONS,
    NET_CONTENTS_REREAD,
    SYSTEM_PROMPT,
    clamp_confidences,
    parse_json_object,
)
from app.extraction.imaging import DEFAULT_TARGET_LONG_EDGE, upscale_image
from app.extraction.provider import VisionProvider
from app.extraction.schema import ExtractedField, ExtractedLabel
from app.extraction.tls import use_system_trust_store

_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class OpenAIVisionProvider(VisionProvider):
    def __init__(
        self,
        api_key: str | None,
        model: str,
        max_tokens: int,
        timeout: float,
        max_retries: int = 1,
        upscale_target: int | None = DEFAULT_TARGET_LONG_EDGE,
    ):
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Set it, or run with TTB_VISION_PROVIDER=fake for offline mode."
            )
        use_system_trust_store()
        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._model = model
        self._max_tokens = max_tokens
        # Enlarge small label images so the model can read fine print (e.g. the
        # back-label "Imported by ..." line); None disables it.
        self._upscale_target = upscale_target

    def extract(self, images: list[LabelImage]) -> ExtractedLabel:
        if not images:
            return ExtractedLabel(image_quality="low", notes="No label images provided.")

        content: list[dict] = [{"type": "input_text", "text": SYSTEM_PROMPT}]
        for idx, img in enumerate(images):
            if self._upscale_target:
                data, fmt = upscale_image(img.data, img.image_format, self._upscale_target)
            else:
                data, fmt = img.data, img.image_format
            mime = _MEDIA_TYPES.get((fmt or "").lower(), "image/jpeg")
            label = img.image_type or "label"
            content.append({"type": "input_text", "text": f"Image index {idx} ({label}):"})
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{base64.standard_b64encode(data).decode('ascii')}",
                    "detail": "high",
                }
            )
        content.append({"type": "input_text", "text": EXTRACTION_INSTRUCTIONS})

        response = self._client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": content}],
            max_output_tokens=self._max_tokens,
        )
        data = parse_json_object(response.output_text)
        return clamp_confidences(ExtractedLabel.model_validate(data))

    def extract_net_contents(self, images: list[LabelImage]) -> ExtractedField:
        """Targeted re-read of only the net contents — recovers a first-pass miss on hard
        layouts (e.g. a circular keg collar) by focusing the model on that one field."""
        if not images:
            return ExtractedField()
        content: list[dict] = [{"type": "input_text", "text": SYSTEM_PROMPT}]
        for idx, img in enumerate(images):
            if self._upscale_target:
                data, fmt = upscale_image(img.data, img.image_format, self._upscale_target)
            else:
                data, fmt = img.data, img.image_format
            mime = _MEDIA_TYPES.get((fmt or "").lower(), "image/jpeg")
            content.append({"type": "input_text", "text": f"Image index {idx}:"})
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{base64.standard_b64encode(data).decode('ascii')}",
                    "detail": "high",
                }
            )
        content.append({"type": "input_text", "text": NET_CONTENTS_REREAD})

        response = self._client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": content}],
            max_output_tokens=256,
        )
        data = parse_json_object(response.output_text)
        value = data.get("value")
        present = bool(data.get("present")) and bool(value)
        try:
            conf = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        return ExtractedField(
            value=value if present else None,
            present=present,
            confidence=conf,
            source_image=data.get("source_image"),
        )
