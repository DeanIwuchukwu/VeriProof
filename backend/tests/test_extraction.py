"""Extraction provider wiring + full in-memory pipeline (no network).

Uses the FakeVisionProvider so the extract -> match pipeline is exercised end-to-end
without an API key. The real Anthropic provider is verified in the e2e phase (WBS 6.8).
"""

import pytest

from app.cola.models import ClaimedFields, ProductSource, ProductType
from app.config import Settings
from app.extraction.extractor import Extractor
from app.extraction.provider import FakeVisionProvider, get_vision_provider
from app.matching.engine import MatchEngine
from app.matching.verdict import Status


def test_factory_returns_fake_for_fake_setting():
    provider = get_vision_provider(Settings(TTB_VISION_PROVIDER="fake"))
    assert isinstance(provider, FakeVisionProvider)


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown vision provider"):
        get_vision_provider(Settings(TTB_VISION_PROVIDER="bogus"))


def test_anthropic_provider_without_key_raises():
    # Selecting anthropic with no key must fail fast with a helpful message, not at call time.
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_vision_provider(Settings(TTB_VISION_PROVIDER="anthropic", ANTHROPIC_API_KEY=None))


def test_full_pipeline_fake_provider_passes():
    extractor = Extractor(provider=FakeVisionProvider())
    extracted = extractor.extract(images=[])  # fake ignores images
    claimed = ClaimedFields(
        brand_name="OLD TOM DISTILLERY",
        product_type=ProductType.DISTILLED_SPIRITS,
        source=ProductSource.DOMESTIC,
        net_contents=["750 MILLILITERS"],
        alcohol_content="45",
        class_type_description="WHISKY",
        applicant_name_address="OLD TOM DISTILLERY, INC.",
    )
    result = MatchEngine().verify(claimed, extracted)
    assert result.overall == Status.PASS
