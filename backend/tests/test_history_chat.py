from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import db
from app.cola.models import ClaimedFields, ColaRecord
from app.history_chat import (
    HistoryChatResponse,
    _detect_exact_field,
    _extract_exact_field_from_pdf,
    get_history_chat_service,
)
from app.main import app
from app.matching.verdict import FieldVerdict, Status, VerificationResult

REPO_ROOT = Path(__file__).resolve().parents[2]
COLA_DIR = REPO_ROOT / "ColaData"


class StubChatService:
    def __init__(self):
        self.requests = []

    def answer(self, req):
        self.requests.append(req)
        return HistoryChatResponse(
            answer="Based on the saved history, this is the BARENJAGER record.",
            citations=[
                {
                    "verification_id": req.visible_items[0].verification_id,
                    "filename": req.visible_items[0].filename,
                    "ttb_id": req.visible_items[0].ttb_id,
                    "source": "history",
                }
            ],
            pdf_used=False,
        )


class BrokenChatService:
    def answer(self, req):
        raise ValueError("OPENAI_API_KEY is not set.")


@pytest.fixture(autouse=True)
def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.use_engine(engine)
    yield
    db.reset()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _seed_saved_record() -> str:
    pdf = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()
    result = VerificationResult(
        fields=[FieldVerdict(field="brand_name", label="Brand Name", status=Status.PASS)]
    )
    result.compute_overall()
    result.processing_ms = 3200
    record = ColaRecord(claimed=ClaimedFields(ttb_id="11038001000725", brand_name="BARENJAGER"))
    vid = db.save_verification(source="upload", result=result, record=record, filename="OMB No. 1513-0020.pdf", pdf=pdf)
    assert vid is not None
    return vid


def test_history_chat_returns_answer_and_citations(client: TestClient):
    vid = _seed_saved_record()
    stub = StubChatService()
    app.dependency_overrides[get_history_chat_service] = lambda: stub

    r = client.post(
        "/api/history/chat",
        json={
            "message": "Tell me about the BARENJAGER record.",
            "open_verification_id": vid,
            "visible_items": [
                {
                    "verification_id": vid,
                    "created_at": None,
                    "source": "upload",
                    "filename": "OMB No. 1513-0020.pdf",
                    "ttb_id": "11038001000725",
                    "brand_name": "BARENJAGER",
                    "product_type": "DISTILLED SPIRITS",
                    "overall": "PASS",
                    "processing_ms": 3200,
                    "has_pdf": True,
                    "decision": None,
                }
            ],
            "recent_turns": [{"role": "user", "content": "What did we verify?"}],
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert "BARENJAGER" in body["answer"]
    assert body["pdf_used"] is False
    assert body["citations"][0]["verification_id"] == vid
    assert stub.requests[0].open_verification_id == vid


def test_history_chat_surfaces_service_errors(client: TestClient):
    _seed_saved_record()
    app.dependency_overrides[get_history_chat_service] = lambda: BrokenChatService()

    r = client.post(
        "/api/history/chat",
        json={"message": "What does the PDF say?", "open_verification_id": None, "visible_items": [], "recent_turns": []},
    )

    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


@pytest.mark.parametrize(
    ("question", "field_name"),
    [
        ("What is their fax number?", "fax_number"),
        ("What is the phone number?", "phone_number"),
        ("What is the email address?", "email_address"),
        ("What is the serial number?", "serial_number"),
        ("What is the formula number?", "formula"),
        ("What is the TTB ID?", "ttb_id"),
        ("What is the applicant address?", "applicant_name_address"),
        ("What is the brand name?", "brand_name"),
        ("What is the fanciful name?", "fanciful_name"),
        ("What is the ABV?", "alcohol_content"),
        ("What are the net contents?", "net_contents"),
    ],
)
def test_detect_exact_field(question: str, field_name: str):
    assert _detect_exact_field(question) == field_name


def test_extract_exact_field_from_pdf_returns_common_form_values():
    pdf = (COLA_DIR / "OMB No. 1513-0023.pdf").read_bytes()

    fax = _extract_exact_field_from_pdf(pdf, "fax_number")
    phone = _extract_exact_field_from_pdf(pdf, "phone_number")
    serial = _extract_exact_field_from_pdf(pdf, "serial_number")
    formula = _extract_exact_field_from_pdf(pdf, "formula")
    ttb_id = _extract_exact_field_from_pdf(pdf, "ttb_id")
    brand = _extract_exact_field_from_pdf(pdf, "brand_name")
    fanciful = _extract_exact_field_from_pdf(pdf, "fanciful_name")
    alcohol = _extract_exact_field_from_pdf(pdf, "alcohol_content")
    net_contents = _extract_exact_field_from_pdf(pdf, "net_contents")
    applicant = _extract_exact_field_from_pdf(pdf, "applicant_name_address")

    assert fax == {
        "label": "FAX NUMBER",
        "value": "(202) 591-2977",
        "page": 1,
        "snippet": "17. FAX NUMBER | (202) 591-2977 | 19. SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE CONTAINER (e.g., net contents) ONLY IF",
    }
    assert phone["value"] == "(202) 756-8406"
    assert phone["page"] == 1
    assert serial["value"] == "14MW14"
    assert formula["value"] == "1211770"
    assert ttb_id["value"] == "14351001000537"
    assert brand["value"] == "SORTILEGE"
    assert fanciful["value"] == "MAPLE CREAM"
    assert alcohol["value"] == "17"
    assert "750 MILLILITERS" in (net_contents["value"] or "")
    assert "SIDNEY FRANK IMPORTING CO., INC." in (applicant["value"] or "")
