"""Data models for a parsed COLA record.

A COLA record (TTB Form 5100.31) bundles the *claimed* application fields and the
affixed label image(s) in one document. These models hold the result of parsing
that record; the verification engine consumes `ClaimedFields` and the label images.

See docs/SPEC.md §4 for the field semantics that drive matching.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProductType(str, Enum):
    """TTB "TYPE OF PRODUCT" — drives beverage-type required-field rules."""

    WINE = "WINE"
    DISTILLED_SPIRITS = "DISTILLED SPIRITS"
    MALT_BEVERAGE = "MALT BEVERAGE"
    UNKNOWN = "UNKNOWN"


class ProductSource(str, Enum):
    """TTB "SOURCE OF PRODUCT" — country-of-origin is required iff IMPORTED."""

    DOMESTIC = "DOMESTIC"
    IMPORTED = "IMPORTED"
    UNKNOWN = "UNKNOWN"


class LabelImage(BaseModel):
    """One affixed label image extracted from the COLA record.

    `data` carries the raw image bytes for in-memory processing (stateless — never
    persisted, per SPEC N4). It is excluded from serialized output by default.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_type: str | None = Field(
        default=None,
        description='COLA "Image Type" label, e.g. "Brand (front) or keg collar", "Back", "Other".',
    )
    actual_dimensions: str | None = Field(
        default=None,
        description='COLA "Actual Dimensions" string, e.g. "1.81 inches W X 2.28 inches H".',
    )
    width_px: int = 0
    height_px: int = 0
    image_format: str = "png"
    page_index: int = 0
    data: bytes = Field(default=b"", repr=False, exclude=True)

    @property
    def size_bytes(self) -> int:
        return len(self.data)


class ClaimedFields(BaseModel):
    """The application's claimed values, parsed from the COLA form layer.

    All fields are optional: a robust parser records what it reliably finds and
    leaves the rest `None`/`UNKNOWN` rather than guessing. Checkbox-driven fields
    (`product_type`, `source`) may be `UNKNOWN` when the text layer alone is
    insufficient — the LLM/vision fallback fills these (SPEC §7, WBS 2.3).
    """

    ttb_id: str | None = None
    serial_number: str | None = None
    brand_name: str | None = None
    fanciful_name: str | None = None
    product_type: ProductType = ProductType.UNKNOWN
    source: ProductSource = ProductSource.UNKNOWN
    # Net contents may list several allowed sizes (e.g. 375/750 mL/1 L, or keg sizes).
    net_contents: list[str] = Field(default_factory=list)
    alcohol_content: str | None = None  # raw as printed, e.g. "35", "11.5"
    class_type_description: str | None = None  # TTB internal code, not verbatim on label
    applicant_name_address: str | None = None
    dba_tradename: str | None = None  # the "... (Used on label)" trade name
    formula: str | None = None


class ColaRecord(BaseModel):
    """A fully parsed COLA record: claimed fields + label images + provenance."""

    claimed: ClaimedFields
    label_images: list[LabelImage] = Field(default_factory=list)
    form_version: str | None = None  # e.g. "TTB F 5100.31 (5/2011)"
    # Raw extracted form text — retained in-memory for the LLM fallback / debugging.
    raw_text: str | None = Field(default=None, repr=False, exclude=True)

    @property
    def image_count(self) -> int:
        return len(self.label_images)
