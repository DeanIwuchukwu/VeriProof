"""Anthropic Claude vision provider.

Sends the full label image set in one request and forces a structured ExtractedLabel
back via `messages.parse` (the model must populate the schema — no free-text parsing).
Thinking is disabled to stay inside the <5s latency budget; the task is transcription,
not deep reasoning.
"""

from __future__ import annotations

import base64
import json

import anthropic

from app.cola.models import LabelImage
from app.extraction.provider import VisionProvider
from app.extraction.schema import ExtractedLabel

_TRUST_STORE_READY = False


def _use_system_trust_store() -> None:
    """Trust the OS certificate store for TLS.

    Behind corporate/endpoint TLS interception (e.g. an SSL-inspecting proxy that
    re-signs HTTPS with a private root CA), Python's bundled `certifi` store does not
    contain that CA, so requests fail with CERTIFICATE_VERIFY_FAILED. The Windows/macOS
    trust store does contain it. `truststore` routes verification through the OS store —
    keeping verification ON, unlike the unsafe `verify=False` shortcut. Best-effort:
    on machines without interception this is a harmless no-op.
    """
    global _TRUST_STORE_READY
    if _TRUST_STORE_READY:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 — fall back to certifi if unavailable
        pass
    _TRUST_STORE_READY = True

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

# Each label field is reported as this object.
_FIELD_SHAPE = '{"value": string|null, "present": boolean, "confidence": number 0..1, "source_image": int|null}'

EXTRACTION_INSTRUCTIONS = (
    "Read the TTB label field values from the image(s) above and return them as a single JSON object.\n\n"
    "Output ONLY the JSON object — no markdown fences, no commentary before or after.\n\n"
    "The JSON object must have exactly these keys:\n"
    f'  "brand_name": {_FIELD_SHAPE},        (the brand / company name)\n'
    f'  "fanciful_name": {_FIELD_SHAPE},      (the specific product / fanciful name, if distinct)\n'
    f'  "class_type": {_FIELD_SHAPE},         (class/type designation exactly as printed)\n'
    f'  "alcohol_content": {_FIELD_SHAPE},    (as printed, include proof if shown, e.g. "45% Alc./Vol. (90 Proof)")\n'
    f'  "net_contents": {_FIELD_SHAPE},       (as printed, e.g. "750 mL")\n'
    f'  "producer_name": {_FIELD_SHAPE},      (the "produced by"/"bottled by"/"brewed by" name as printed)\n'
    f'  "producer_address": {_FIELD_SHAPE},   (its address as printed)\n'
    f'  "importer_name": {_FIELD_SHAPE},      (U.S. importer after "Imported by"/"Imported exclusively by"/"Sole importer"; '
    "for imports this is usually a DIFFERENT company from the foreign producer and is often in small print on the back — "
    'look carefully; null if domestic)\n'
    f'  "country_of_origin": {_FIELD_SHAPE},  (e.g. "Product of France"; null if none)\n'
    f'  "government_warning": {_FIELD_SHAPE}, (the warning text transcribed VERBATIM, preserving exact capitalization)\n'
    '  "warning_prefix_all_caps": boolean|null,  (true ONLY if "GOVERNMENT WARNING:" is in ALL CAPITAL letters)\n'
    '  "warning_appears_bold": boolean|null,     (best-effort visual judgment)\n'
    '  "image_quality": "good"|"fair"|"low",     ("low" if angle/glare/blur make fields unreadable)\n'
    '  "overall_confidence": number 0..1\n\n'
    "Rules: a field is present only if it visibly appears on a label; otherwise present=false, value=null. "
    "Transcribe what you see — do not normalize, translate, or correct the text. Do not guess unreadable text. "
    "For government_warning specifically: if it is printed curved/rotated/radially (e.g. around a keg "
    "collar), in very small print, or is otherwise hard to read, set its confidence below 0.8 to reflect "
    "that you may not have transcribed every word exactly."
)


class AnthropicVisionProvider(VisionProvider):
    def __init__(
        self, api_key: str | None, model: str, max_tokens: int, timeout: float, max_retries: int = 1
    ):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it, or run with TTB_VISION_PROVIDER=fake for offline mode."
            )
        _use_system_trust_store()
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

        # Plain create + JSON-in-prompt (not output_config.format): the structured-output
        # feature can hang behind TLS-inspecting proxies; this path is fast and portable.
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        data = _parse_json_object(text)
        result = ExtractedLabel.model_validate(data)
        return _clamp_confidences(result)


def _parse_json_object(text: str) -> dict:
    """Extract the single JSON object from the model's reply.

    Tolerates accidental markdown fences or stray prose by slicing from the first '{'
    to the last '}'. Raises ValueError (→ friendly API error) if no JSON is present.
    """
    if not text or "{" not in text:
        raise ValueError("The model did not return a readable result for this label.")
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError("The model's label reading could not be parsed as JSON.") from e


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
        "importer_name",
        "country_of_origin",
        "government_warning",
    ):
        field = getattr(label, field_name)
        field.confidence = clamp(field.confidence)
    label.overall_confidence = clamp(label.overall_confidence)
    return label
