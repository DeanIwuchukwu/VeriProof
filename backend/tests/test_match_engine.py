"""Adversarial matching-engine tests — the §4 semantics under hostile inputs.

Each test maps to a traceability test case (TC-02…TC-13 in docs/SPEC.md §8). Defaults
produce a fully-passing record; each test mutates only what it needs to, so a regression
in one rule can't hide behind unrelated fields.
"""

import pytest

from app.cola.models import ClaimedFields, ProductSource, ProductType
from app.extraction.schema import ExtractedField, ExtractedLabel
from app.matching.engine import MatchEngine
from app.matching.verdict import Status
from app.matching.warning_text import CANONICAL_WARNING

ENGINE = MatchEngine()


def ef(value=None, present=True, conf=0.95, src=0) -> ExtractedField:
    return ExtractedField(value=value, present=present and value is not None, confidence=conf, source_image=src)


def make_claimed(**over) -> ClaimedFields:
    base = dict(
        brand_name="OLD TOM DISTILLERY",
        fanciful_name=None,
        product_type=ProductType.DISTILLED_SPIRITS,
        source=ProductSource.IMPORTED,
        net_contents=["750 MILLILITERS"],
        alcohol_content="45",
        class_type_description="WHISKY",
        applicant_name_address="OLD TOM DISTILLERY, INC., LOUISVILLE KY",
        dba_tradename=None,
    )
    base.update(over)
    return ClaimedFields(**base)


def make_extracted(**over) -> ExtractedLabel:
    fields = dict(
        brand_name=ef("Old Tom Distillery"),
        fanciful_name=ef(None),
        class_type=ef("Kentucky Straight Bourbon Whiskey"),
        alcohol_content=ef("45% Alc./Vol. (90 Proof)"),
        net_contents=ef("750 mL"),
        producer_name=ef("Old Tom Distillery"),
        producer_address=ef("Louisville, KY"),
        importer_name=ef(None),
        country_of_origin=ef("Product of Scotland"),
        government_warning=ef(CANONICAL_WARNING),
        warning_prefix_all_caps=True,
        warning_appears_bold=True,
        image_quality="good",
        overall_confidence=0.95,
    )
    fields.update(over)
    return ExtractedLabel(**fields)


def by_field(result, name):
    return next(v for v in result.fields if v.field == name)


# --- baseline ---------------------------------------------------------------

def test_clean_record_passes():
    res = ENGINE.verify(make_claimed(), make_extracted())
    assert res.overall == Status.PASS
    assert by_field(res, "government_warning").status == Status.PASS


# --- TC-02: brand matched via fanciful name --------------------------------

def test_tc02_brand_matches_via_fanciful():
    claimed = make_claimed(brand_name="GEKKEIKAN", fanciful_name="SUZAKU")
    # Model read the dominant text "Suzaku" as the brand and the small text as fanciful.
    extracted = make_extracted(brand_name=ef("Suzaku"), fanciful_name=ef("Gekkeikan"))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "brand_name").status == Status.PASS
    assert "fanciful" in by_field(res, "brand_name").reason.lower()


def test_brand_accent_insensitive():
    # Bärenjäger case: label uses umlauts, application is ASCII uppercase — same brand.
    res = ENGINE.verify(make_claimed(brand_name="BARENJAGER"), make_extracted(brand_name=ef("Bärenjäger")))
    assert by_field(res, "brand_name").status == Status.PASS


# --- TC-03: producer matched via DBA / trade name --------------------------

def test_tc03_producer_matches_via_dba():
    claimed = make_claimed(
        applicant_name_address="PUB DOG BREWING COMPANY, THE D.O.G. BEVERAGE COMPANY, INC.",
        dba_tradename="TWELVE PERCENT",
        product_type=ProductType.MALT_BEVERAGE,
        source=ProductSource.DOMESTIC,
    )
    extracted = make_extracted(producer_name=ef("Twelve Percent"))
    res = ENGINE.verify(claimed, extracted)
    v = by_field(res, "producer_name")
    assert v.status == Status.PASS
    assert "dba" in v.reason.lower() or "trade name" in v.reason.lower()


def test_producer_matches_via_importer():
    # Bärenjäger case: label names the German bottler AND the importer (the applicant).
    claimed = make_claimed(
        applicant_name_address="SIDNEY FRANK IMPORTING CO., INC., 20 CEDAR ST, NEW ROCHELLE NY 10801",
        source=ProductSource.IMPORTED,
    )
    # Realistic: 'Imported by' prefix + a different address than the application.
    extracted = make_extracted(
        producer_name=ef("Teucke & König Bärenfangfabrik"),
        importer_name=ef("IMPORTED BY SIDNEY FRANK IMPORTING CO. INC. NEW ROCHELLE, N.Y."),
    )
    res = ENGINE.verify(claimed, extracted)
    v = by_field(res, "producer_name")
    assert v.status == Status.PASS
    assert "importer" in v.reason.lower()


def test_producer_distinct_company_does_not_match():
    claimed = make_claimed(applicant_name_address="ACME BEVERAGE IMPORTS, INC., CHICAGO IL")
    extracted = make_extracted(
        producer_name=ef("Globex Distilling Company"),
        importer_name=ef("Imported by Wonka Spirits LLC, New York NY"),
    )
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "producer_name").status == Status.FLAG


# --- TC-04: class/type is advisory, never a FAIL ---------------------------

def test_tc04_class_type_is_advisory_not_fail():
    claimed = make_claimed(class_type_description="TABLE RED WINE", product_type=ProductType.WINE)
    extracted = make_extracted(class_type=ef("Red Wine"))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "class_type").status == Status.INFO


# --- TC-05: title-case warning prefix -> FAIL ------------------------------

def test_tc05_warning_title_case_fails():
    titled = CANONICAL_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    extracted = make_extracted(government_warning=ef(titled), warning_prefix_all_caps=False)
    res = ENGINE.verify(make_claimed(), extracted)
    v = by_field(res, "government_warning")
    assert v.status == Status.FAIL
    assert "capital" in v.reason.lower()


# --- TC-06: paraphrased / missing clause -> FAIL ---------------------------

def test_tc06_warning_missing_clause_fails():
    paraphrased = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
        "alcoholic beverages during pregnancy because of the risk of birth defects. "
        "(2) Consumption of alcoholic beverages impairs your ability to drive a car, "
        "and may cause health problems."  # dropped "or operate machinery"
    )
    extracted = make_extracted(government_warning=ef(paraphrased), warning_prefix_all_caps=True)
    res = ENGINE.verify(make_claimed(), extracted)
    assert by_field(res, "government_warning").status == Status.FAIL


# --- TC-07: correctly-read warning (e.g. radial keg collar) -> PASS --------

def test_tc07_warning_read_correctly_passes():
    extracted = make_extracted(government_warning=ef(CANONICAL_WARNING), warning_prefix_all_caps=True)
    res = ENGINE.verify(make_claimed(), extracted)
    assert by_field(res, "government_warning").status == Status.PASS


def test_warning_unverifiable_stylized_flags():
    # Radial keg-collar case: present, ALL-CAPS prefix, but read with low confidence on
    # stylized text → FLAG for human review, NOT a hard FAIL (which would be a false fail).
    garbled = CANONICAL_WARNING.replace(" because of the risk of birth defects", "")
    extracted = make_extracted(
        government_warning=ExtractedField(value=garbled, present=True, confidence=0.55),
        warning_prefix_all_caps=True,
        image_quality="fair",
    )
    res = ENGINE.verify(make_claimed(), extracted)
    v = by_field(res, "government_warning")
    assert v.status == Status.FLAG
    assert "manual" in v.reason.lower()


# --- TC-08: proof != 2 x ABV -> FLAG ---------------------------------------

def test_tc08_proof_inconsistent_flags():
    extracted = make_extracted(alcohol_content=ef("45% Alc./Vol. (80 Proof)"))
    res = ENGINE.verify(make_claimed(alcohol_content="45"), extracted)
    assert by_field(res, "proof_check").status == Status.FLAG
    assert res.overall == Status.FLAG


# --- TC-09: ABV mismatch -> FAIL -------------------------------------------

def test_tc09_abv_mismatch_fails():
    extracted = make_extracted(alcohol_content=ef("45% Alc./Vol. (90 Proof)"))
    res = ENGINE.verify(make_claimed(alcohol_content="40"), extracted)
    v = by_field(res, "alcohol_content")
    assert v.status == Status.FAIL
    assert "40" in v.reason and "45" in v.reason


# --- TC-10: net contents allowed-set ---------------------------------------

def test_tc10_net_contents_in_allowed_set():
    claimed = make_claimed(net_contents=["375 MILLILITERS", "750 MILLILITERS", "1 LITER"])
    extracted = make_extracted(net_contents=ef("750ML"))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "net_contents").status == Status.PASS


def test_net_contents_not_in_allowed_set_fails():
    claimed = make_claimed(net_contents=["375 MILLILITERS", "750 MILLILITERS"])
    extracted = make_extracted(net_contents=ef("1 Liter"))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "net_contents").status == Status.FAIL


# --- TC-11: imported missing country of origin -> FAIL ---------------------

def test_tc11_imported_missing_country_fails():
    extracted = make_extracted(country_of_origin=ef(None))
    res = ENGINE.verify(make_claimed(source=ProductSource.IMPORTED), extracted)
    assert by_field(res, "country_of_origin").status == Status.FAIL


def test_domestic_missing_country_is_info():
    extracted = make_extracted(country_of_origin=ef(None))
    res = ENGINE.verify(make_claimed(source=ProductSource.DOMESTIC), extracted)
    assert by_field(res, "country_of_origin").status == Status.INFO


# --- TC-12: domestic malt beverage missing ABV -> INFO, not FAIL -----------

def test_tc12_malt_missing_abv_is_optional():
    claimed = make_claimed(product_type=ProductType.MALT_BEVERAGE, source=ProductSource.DOMESTIC)
    extracted = make_extracted(alcohol_content=ef(None))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "alcohol_content").status == Status.INFO


def test_spirits_missing_abv_fails():
    claimed = make_claimed(product_type=ProductType.DISTILLED_SPIRITS)
    extracted = make_extracted(alcohol_content=ef(None))
    res = ENGINE.verify(claimed, extracted)
    assert by_field(res, "alcohol_content").status == Status.FAIL


# --- TC-13: low image quality never reads as a confident PASS --------------

def test_tc13_low_image_quality_no_false_pass():
    extracted = make_extracted(image_quality="low")  # otherwise-passing fields
    res = ENGINE.verify(make_claimed(), extracted)
    assert res.overall != Status.PASS
    assert res.notes and "image quality" in res.notes.lower()


# --- extract-only mode (manual entry with no claimed values) ---------------

def test_extract_only_shows_info_not_false_verdicts():
    claimed = ClaimedFields()  # nothing claimed
    res = ENGINE.verify(claimed, make_extracted())
    # brand/net/abv become INFO (nothing to compare); warning still strictly checked.
    assert by_field(res, "brand_name").status == Status.INFO
    assert by_field(res, "government_warning").status == Status.PASS


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("STONE'S THROW", "Stone's Throw", True),
        ("Château Lafite", "Chateau  Lafite", True),
        ("Bärenjäger", "BARENJAGER", True),
        ("Old Tom", "Completely Different", False),
    ],
)
def test_fuzzy_brand_equivalence(a, b, expected):
    from app.matching.normalize import fuzzy_equal

    assert fuzzy_equal(a, b) is expected
