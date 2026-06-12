"""ColaParser must read all five real COLA records correctly (SPEC WBS 2.4, milestone M1).

Ground truth is taken directly from the records in /ColaData. These assertions are the
proof that the parser reads real government data, not a synthetic happy path.
"""

from pathlib import Path

import pytest

from app.cola.models import ProductSource, ProductType
from app.cola.parser import ColaParser

# (filename, expected dict). Fields we are confident about are asserted exactly;
# fuzzy/long fields (applicant) are asserted by substring.
CASES = [
    (
        "OMB No. 1513-0020.pdf",  # Bärenjäger Honey Liqueur — imported spirit
        {
            "ttb_id": "11038001000725",
            "serial_number": "11MW01",
            "brand_name": "BARENJAGER",
            "fanciful_name": None,
            "product_type": ProductType.DISTILLED_SPIRITS,
            "source": ProductSource.IMPORTED,
            "net_contents": ["50 MILLILITERS"],
            "alcohol_content": "35",
            "class_type": "OTHER HERB & SEED CORDIALS/LIQUEURS",
            "applicant_contains": "SIDNEY FRANK IMPORTING",
            "dba": None,
            "image_count": 2,
        },
    ),
    (
        "OMB No. 1512-0092.pdf",  # Cascade Val — domestic table red wine (older form)
        {
            "ttb_id": "03211001000018",
            "serial_number": "030035",
            "brand_name": "CASCADE WINERY",
            "fanciful_name": "CASCADE VAL",
            "product_type": ProductType.WINE,
            "net_contents": ["750 MILLILITERS"],
            "alcohol_content": "11.5",
            "class_type": "TABLE RED WINE",
            "applicant_contains": "CASCADE WINERY",
            "dba": "CASCADE WINERY",
            "image_count": 1,
        },
    ),
    (
        "OMB No. 1513-0020_2.pdf",  # Jacques Cardin Jasmin VSOP — imported cognac, multi-size
        {
            "ttb_id": "11262001000022",
            "serial_number": "11MW05",
            "brand_name": "JACQUES CARDIN",
            "fanciful_name": "JASMIN",
            "product_type": ProductType.DISTILLED_SPIRITS,
            "source": ProductSource.IMPORTED,
            "net_contents": ["375 MILLILITERS", "750 MILLILITERS", "1 LITER"],
            "alcohol_content": "40",
            "class_type": "OTHER SPECIALTIES & PROPRIETARIES",
            "image_count": 2,
        },
    ),
    (
        "OMB No. 1513-0020_3.pdf",  # Stillwater Artisanal Debutante — domestic flavored ale, DBA
        {
            "ttb_id": "11364001000181",
            "serial_number": "110125",
            "brand_name": "STILLWATER ARTISANAL",
            "fanciful_name": "DEBUTANTE",
            "product_type": ProductType.MALT_BEVERAGE,
            "source": ProductSource.DOMESTIC,
            "net_contents": ["5.17 gal.", "5.4 gal.", "10.8 gal.", "15.5 gal."],
            "alcohol_content": "6.8",
            "class_type": "MALT BEVERAGES SPECIALITIES - FLAVORED",
            "applicant_contains": "PUB DOG BREWING",
            "dba": "TWELVE PERCENT",
            "image_count": 1,
        },
    ),
    (
        "OMB No. 1513-0020_4.pdf",  # Gekkeikan "Suzaku" Junmai Ginjo — imported sake
        {
            "ttb_id": "13100001000426",
            "serial_number": "13MW04",
            "brand_name": "GEKKEIKAN",
            "fanciful_name": "SUZAKU",
            "product_type": ProductType.WINE,
            "source": ProductSource.IMPORTED,
            "alcohol_content": "15.5",
            "class_type": "SAKE - IMPORTED",
            "applicant_contains": "SIDNEY FRANK IMPORTING",
            "image_count": 2,
        },
    ),
]


@pytest.fixture(scope="module")
def parser() -> ColaParser:
    return ColaParser()


@pytest.mark.parametrize("filename,expected", CASES, ids=[c[0] for c in CASES])
def test_parses_real_record(parser: ColaParser, cola_dir: Path, filename: str, expected: dict):
    rec = parser.parse(cola_dir / filename)
    c = rec.claimed

    assert c.ttb_id == expected["ttb_id"]
    assert c.serial_number == expected["serial_number"]
    assert c.brand_name == expected["brand_name"]
    assert c.fanciful_name == expected.get("fanciful_name", c.fanciful_name)
    assert c.product_type == expected["product_type"]
    if "source" in expected:
        assert c.source == expected["source"]
    if "net_contents" in expected:
        assert c.net_contents == expected["net_contents"]
    assert c.alcohol_content == expected["alcohol_content"]
    assert c.class_type_description == expected["class_type"]
    if "applicant_contains" in expected:
        assert c.applicant_name_address is not None
        assert expected["applicant_contains"] in c.applicant_name_address
    if "dba" in expected:
        assert c.dba_tradename == expected["dba"]
    assert rec.image_count == expected["image_count"]


@pytest.mark.parametrize("filename,expected", CASES, ids=[c[0] for c in CASES])
def test_label_images_have_data(parser: ColaParser, cola_dir: Path, filename: str, expected: dict):
    rec = parser.parse(cola_dir / filename)
    assert len(rec.label_images) == expected["image_count"]
    for img in rec.label_images:
        assert img.size_bytes > 1000, "label image should carry real bytes"
        assert img.width_px > 0 and img.height_px > 0
        assert img.image_format in {"jpeg", "jpg", "png"}


def test_form_version_detected(parser: ColaParser, cola_dir: Path):
    rec = parser.parse(cola_dir / "OMB No. 1513-0020_2.pdf")
    assert rec.form_version is not None
    assert "5100.31" in rec.form_version
