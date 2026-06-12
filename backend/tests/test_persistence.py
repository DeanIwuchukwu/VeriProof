"""Persistence tests — verifications (incl. stored PDF) and reviewer decisions.

Runs fully offline: FakeVisionProvider for extraction and an in-memory SQLite
engine bound via `db.use_engine` (production uses PostgreSQL; the schema types
used — JSON, LargeBinary — behave identically through SQLAlchemy).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import db
from app.extraction.extractor import Extractor
from app.extraction.provider import FakeVisionProvider
from app.main import app, get_service
from app.service import VerificationService

REPO_ROOT = Path(__file__).resolve().parents[2]
COLA_DIR = REPO_ROOT / "ColaData"
PDF = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()


@pytest.fixture(autouse=True)
def _fake_service_and_db():
    app.dependency_overrides[get_service] = lambda: VerificationService(
        extractor=Extractor(provider=FakeVisionProvider())
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.use_engine(engine)
    yield
    db.reset()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _verify(client: TestClient) -> dict:
    r = client.post("/api/verify/cola", files={"file": ("cola.pdf", PDF, "application/pdf")})
    assert r.status_code == 200
    return r.json()


def test_verify_returns_verification_id(client: TestClient):
    body = _verify(client)
    assert isinstance(body["verification_id"], str) and len(body["verification_id"]) == 32


def test_decision_roundtrip_and_append_only(client: TestClient):
    vid = _verify(client)["verification_id"]

    r = client.post(f"/api/verifications/{vid}/decision", json={"action": "ACCEPT", "note": "looks good"})
    assert r.status_code == 200
    assert r.json()["action"] == "ACCEPT"
    assert r.json()["note"] == "looks good"

    # Re-deciding appends; it never overwrites (audit trail).
    r = client.post(f"/api/verifications/{vid}/decision", json={"action": "REJECT"})
    assert r.status_code == 200

    record = client.get(f"/api/verifications/{vid}").json()
    actions = [d["action"] for d in record["decisions"]]
    assert actions == ["ACCEPT", "REJECT"]
    assert record["brand_name"] == "BARENJAGER"
    assert record["overall"] in {"PASS", "FLAG", "FAIL"}

    # Listing shows the latest decision.
    items = client.get("/api/verifications").json()["items"]
    assert items[0]["verification_id"] == vid
    assert items[0]["decision"]["action"] == "REJECT"


def test_pdf_roundtrip(client: TestClient):
    vid = _verify(client)["verification_id"]
    r = client.get(f"/api/verifications/{vid}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == PDF  # byte-identical to the upload


def test_manual_record_has_no_pdf(client: TestClient):
    r = client.post(
        "/api/verify/manual",
        data={"brand_name": "OLD TOM DISTILLERY"},
        files={"images": ("label.jpg", b"\xff\xd8\xff fake-jpeg", "image/jpeg")},
    )
    assert r.status_code == 200
    vid = r.json()["verification_id"]
    assert isinstance(vid, str)
    assert client.get(f"/api/verifications/{vid}/pdf").status_code == 404


def test_unknown_verification_404s(client: TestClient):
    assert client.post("/api/verifications/nope/decision", json={"action": "ACCEPT"}).status_code == 404
    assert client.get("/api/verifications/nope").status_code == 404


def test_invalid_action_422s(client: TestClient):
    vid = _verify(client)["verification_id"]
    r = client.post(f"/api/verifications/{vid}/decision", json={"action": "MAYBE"})
    assert r.status_code == 422


def test_batch_items_persist(client: TestClient):
    r = client.post(
        "/api/verify/batch", files=[("files", ("one.pdf", PDF, "application/pdf"))]
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert isinstance(item["verification_id"], str)
    # The stored record carries the PDF.
    assert client.get(f"/api/verifications/{item['verification_id']}/pdf").status_code == 200


def test_repeat_upload_surfaces_prior_decisions(client: TestClient):
    first = _verify(client)
    assert first["prior_verifications"] == []  # nothing earlier
    vid = first["verification_id"]
    client.post(f"/api/verifications/{vid}/decision", json={"action": "ACCEPT", "note": "ok"})

    second = _verify(client)  # same PDF again
    prior = second["prior_verifications"]
    assert len(prior) == 1
    assert prior[0]["verification_id"] == vid
    assert prior[0]["decision"]["action"] == "ACCEPT"
    # Append-only: both runs exist independently in the saved list.
    assert len(client.get("/api/verifications").json()["items"]) == 2


def test_delete_verification(client: TestClient):
    vid = _verify(client)["verification_id"]
    client.post(f"/api/verifications/{vid}/decision", json={"action": "REJECT"})

    assert client.delete(f"/api/verifications/{vid}").status_code == 204
    assert client.get(f"/api/verifications/{vid}").status_code == 404  # gone (decisions cascade)
    assert client.get("/api/verifications").json()["items"] == []
    assert client.delete(f"/api/verifications/{vid}").status_code == 404  # idempotent-ish


def test_persistence_disabled_yields_null_id(client: TestClient):
    db.reset()  # simulate missing DATABASE_URL
    body = _verify(client)
    assert body["verification_id"] is None
    assert client.get("/api/verifications").status_code == 503
