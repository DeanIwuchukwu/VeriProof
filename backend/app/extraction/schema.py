"""The extraction contract: what the vision step reads off the label image(s).

This is the boundary between the vision provider (which may hallucinate) and the
matching engine (which is deterministic). The provider is forced to return this exact
shape; the engine consumes it. Aggregated across all label images in a record, with
each field noting which image it came from (SPEC §4 — multi-image aggregation).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """One field read from the label artwork."""

    value: str | None = Field(default=None, description="Text as read, verbatim. null if not found.")
    present: bool = Field(default=False, description="Whether the field appears on any label.")
    # 0..1 — not range-constrained here because structured-output JSON schemas don't
    # support numeric bounds; the extractor clamps defensively instead.
    confidence: float = Field(default=0.0, description="Reader's confidence, 0..1.")
    source_image: int | None = Field(default=None, description="Index of the label image it was read from.")


class ExtractedLabel(BaseModel):
    """Structured reading of a full label set (front/back/other), aggregated."""

    brand_name: ExtractedField = Field(default_factory=ExtractedField)
    fanciful_name: ExtractedField = Field(default_factory=ExtractedField)
    class_type: ExtractedField = Field(default_factory=ExtractedField)
    alcohol_content: ExtractedField = Field(default_factory=ExtractedField)
    net_contents: ExtractedField = Field(default_factory=ExtractedField)
    producer_name: ExtractedField = Field(default_factory=ExtractedField)
    producer_address: ExtractedField = Field(default_factory=ExtractedField)
    # Imports often carry BOTH a producer/bottler and a separate importer; either may be
    # the party named on the application (SPEC §4 — name∪DBA matching).
    importer_name: ExtractedField = Field(default_factory=ExtractedField)
    country_of_origin: ExtractedField = Field(default_factory=ExtractedField)
    government_warning: ExtractedField = Field(default_factory=ExtractedField)

    # Warning rendering judgments — made by the vision model from the image itself,
    # since casing/bold are visual properties the text alone can't convey (SPEC §4).
    warning_prefix_all_caps: bool | None = Field(
        default=None, description='Is the "GOVERNMENT WARNING:" prefix in ALL CAPITALS?'
    )
    warning_appears_bold: bool | None = Field(
        default=None, description="Best-effort: does the warning prefix appear bold? (advisory)"
    )

    # Image-quality signal so low-confidence reads surface as "rescan", never false PASS.
    image_quality: str = Field(default="good", description='"good" | "fair" | "low"')
    overall_confidence: float = Field(default=0.0, description="Overall reader confidence, 0..1.")
    notes: str | None = None
