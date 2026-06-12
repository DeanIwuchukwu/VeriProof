"""Beverage-type-aware required-field rules (SPEC F4.8).

Which mandatory items must appear on a label varies by product type and source.
A field that is *required* and missing is a FAIL; a field that is *optional* and
missing is INFO (e.g. a domestic malt beverage need not state ABV federally).

These are pragmatic encodings of 27 CFR parts 4 (wine), 5 (spirits), 7 (malt),
and 16 (warning) sufficient for the prototype; edge cases are documented as
limitations rather than silently assumed.
"""

from __future__ import annotations

from app.cola.models import ProductSource, ProductType

# Fields always required regardless of beverage type.
_ALWAYS_REQUIRED = {"brand_name", "class_type", "net_contents", "government_warning"}

# ABV requirement by product type. Federally, malt-beverage ABV is optional;
# spirits and wine must state alcohol content.
_ABV_REQUIRED = {ProductType.DISTILLED_SPIRITS, ProductType.WINE}


def is_required(field: str, product_type: ProductType, source: ProductSource) -> bool:
    """Whether a missing field should be treated as a violation (FAIL) vs advisory."""
    if field in _ALWAYS_REQUIRED:
        return True
    if field == "alcohol_content":
        return product_type in _ABV_REQUIRED
    if field == "country_of_origin":
        return source == ProductSource.IMPORTED
    # producer name/address: required content, but lenient matching elsewhere.
    return field in {"producer_name", "producer_address"}
