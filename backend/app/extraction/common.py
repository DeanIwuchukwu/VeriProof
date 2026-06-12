"""Shared prompt + parsing helpers for vision providers."""

from __future__ import annotations

import json

from app.extraction.schema import ExtractedLabel

SYSTEM_PROMPT = (
    "You are a TTB compliance assistant that reads U.S. alcohol-beverage label artwork and "
    "transcribes the required label fields. You are precise and literal: you report only what is "
    "actually printed on the label image(s). You never invent or infer values that are not visibly "
    "present. The label set may include a front, a back, and other pieces (capsule/keg collar) of "
    "ONE product; treat them together and note which image each value came from."
)

_FIELD_SHAPE = '{"value": string|null, "present": boolean, "confidence": number 0..1, "source_image": int|null}'

EXTRACTION_INSTRUCTIONS = (
    "Read the TTB label field values from the image(s) above and return them as a single JSON object.\n\n"
    "Output ONLY the JSON object; no markdown fences, no commentary before or after.\n\n"
    "The JSON object must have exactly these keys:\n"
    f'  "brand_name": {_FIELD_SHAPE},        (the brand / company name)\n'
    f'  "fanciful_name": {_FIELD_SHAPE},      (the specific product / fanciful name, if distinct)\n'
    f'  "class_type": {_FIELD_SHAPE},         (class/type designation exactly as printed)\n'
    f'  "alcohol_content": {_FIELD_SHAPE},    (as printed, include proof if shown, e.g. "45% Alc./Vol. (90 Proof)")\n'
    f'  "net_contents": {_FIELD_SHAPE},       (as printed, e.g. "750 mL")\n'
    f'  "producer_name": {_FIELD_SHAPE},      (the "produced by"/"bottled by"/"brewed by" name as printed)\n'
    f'  "producer_address": {_FIELD_SHAPE},   (its address as printed)\n'
    f'  "importer_name": {_FIELD_SHAPE},      (U.S. importer after "Imported by"/"Imported exclusively by"/"Sole importer"; '
    "for imports this is usually a DIFFERENT company from the foreign producer and is often in small print on the back; "
    'look carefully; null if domestic)\n'
    f'  "country_of_origin": {_FIELD_SHAPE},  (e.g. "Product of France"; null if none)\n'
    f'  "government_warning": {_FIELD_SHAPE}, (the warning text transcribed VERBATIM, preserving exact capitalization)\n'
    '  "warning_prefix_all_caps": boolean|null,  (true ONLY if "GOVERNMENT WARNING:" is in ALL CAPITAL letters)\n'
    '  "warning_appears_bold": boolean|null,     (best-effort visual judgment)\n'
    '  "image_quality": "good"|"fair"|"low",     ("low" if angle/glare/blur make fields unreadable)\n'
    '  "overall_confidence": number 0..1\n\n'
    "Rules: a field is present only if it visibly appears on a label; otherwise present=false, value=null. "
    "Transcribe what you see; do not normalize, translate, or correct the text. Do not guess unreadable text. "
    "For imported products, inspect the back label very carefully for the U.S. importer line in small print. "
    "Look specifically for phrases such as 'Imported by', 'Imported exclusively by', or 'Sole importer'. "
    "The importer_name must be the U.S. company name that follows that phrase, not the foreign producer and not a country statement like "
    "'Imported from Germany' or 'Product of France'. If both a foreign producer/bottler and a U.S. importer appear, capture both separately. "
    "If a back label exists, do not leave importer_name null until you have checked that back label for small-print importer text. "
    "For government_warning specifically: if it is printed curved/rotated/radially (e.g. around a keg "
    "collar), in very small print, or is otherwise hard to read, set its confidence below 0.8 to reflect "
    "that you may not have transcribed every word exactly."
)

# Focused, single-field prompt used to recover a first-pass net-contents miss (a targeted
# re-read). It nudges the model on WHERE/WHAT FORMAT to look — not the answer — so it does
# not bias the independent verification.
NET_CONTENTS_REREAD = (
    "Look again at the alcohol-beverage label image(s) for ONE thing only: the NET CONTENTS "
    "(container fill / size). It may be a single value such as '750 mL', '12 FL OZ', or '1.5 L'. "
    "On kegs/barrels it is often a LIST of sizes in gallons (e.g. '5.17 gal., 5.4 gal., 10.8 gal., "
    "15.5 gal.'), sometimes shown as a checkbox list and sometimes wrapped around the curved edge of a "
    "round keg-collar label. Inspect every region, including small print and the edges. Do not report "
    "alcohol content or any other field.\n\n"
    "Output ONLY this JSON object, no commentary:\n"
    f"  {_FIELD_SHAPE}\n"
    "Set present=false and value=null only if you genuinely cannot find any net-contents statement."
)


def parse_json_object(text: str) -> dict:
    """Extract the single JSON object from a model reply."""
    if not text or "{" not in text:
        raise ValueError("The model did not return a readable result for this label.")
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError("The model's label reading could not be parsed as JSON.") from e


def clamp_confidences(label: ExtractedLabel) -> ExtractedLabel:
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
