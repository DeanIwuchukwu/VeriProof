"""Anthropic Claude vision provider.

Sends the full label image set in one request and forces a structured ExtractedLabel
back via `messages.parse` (the model must populate the schema — no free-text parsing).
Thinking is disabled to stay inside the <5s latency budget; the task is transcription,
not deep reasoning.
"""

from __future__ import annotations

import base64

import anthropic

from app.cola.models import LabelImage
from app.extraction.provider import VisionProvider
from app.extraction.schema import ExtractedLabel

_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

SYSTEM_PROMPT = (
    "You are a TTB compliance assistant that reads U.S. alcohol-beverage label artwork and "
    "transcribes the required label fields. You are precise and literal: you report only what is "
    "actually printed on the label image(s). You never invent or infer values that are not visibly "
    "present. The label set may include a front, a back, and other pieces (capsule/keg collar) of "
    "ONE product — treat them together and note which image each value came from."
)

EXTRACTION_INSTRUCTIONS = (
    "Extract the TTB label fields from the image(s) above into the required structure.\n\n"
    "Rules:\n"
    "- A field is present only if it visibly appears on a label. If absent, set present=false and value=null.\n"
    "- brand_name: the brand / company name. fanciful_name: the specific product (fanciful) name, if distinct.\n"
    "- class_type: the class/type designation exactly as printed (e.g. 'Kentucky Straight Bourbon Whiskey').\n"
    "- alcohol_content: as printed, including proof if shown (e.g. '40% ALC./VOL.' or '45% Alc./Vol. (90 Proof)').\n"
    "- net_contents: as printed (e.g. '750 mL', '50 ML').\n"
    "- producer_name / producer_address: the bottler/producer/importer name and address as printed.\n"
    "- country_of_origin: e.g. 'Product of France' / 'Imported from Germany'; null if none.\n"
    "- government_warning: transcribe the warning text VERBATIM, preserving exact capitalization. "
    "Set warning_prefix_all_caps=true ONLY if the 'GOVERNMENT WARNING:' prefix is in ALL CAPITAL letters. "
    "warning_appears_bold is a best-effort visual judgment.\n"
    "- image_quality: 'good' | 'fair' | 'low' based on legibility (angle, glare, blur). If you cannot "
    "read fields reliably, say 'low' rather than guessing.\n"
    "- confidence: 0..1 per field; source_image: the 0-based index of the image you read it from.\n"
    "Transcribe what you see; do not normalize, translate, or correct the text."
)


class AnthropicVisionProvider(VisionProvider):
    def __init__(self, api_key: str | None, model: str, max_tokens: int, timeout: float):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it, or run with TTB_VISION_PROVIDER=fake for offline mode."
            )
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
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

        message = self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "disabled"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_format=ExtractedLabel,
        )
        result = message.parsed_output
        return _clamp_confidences(result)


def _clamp_confidences(label: ExtractedLabel) -> ExtractedLabel:
    """Defensively clamp model-reported confidences into [0, 1]."""

    def clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    for field_name in (
        "brand_name",
        "fanciful_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "producer_name",
        "producer_address",
        "country_of_origin",
        "government_warning",
    ):
        field = getattr(label, field_name)
        field.confidence = clamp(field.confidence)
    label.overall_confidence = clamp(label.overall_confidence)
    return label
