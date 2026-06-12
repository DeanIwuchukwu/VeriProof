"""API endpoint tests using the FakeVisionProvider (no network).

Exercises both input modes end-to-end through FastAPI: COLA upload (mode 1) parses a
real record; manual entry (mode 2) verifies claimed fields against the fake reading.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.extraction.extractor import Extractor
from app.extraction.provider import FakeVisionProvider, VisionProvider
from app.main import app, get_service
from app.service import VerificationService

REPO_ROOT = Path(__file__).resolve().parents[2]
COLA_DIR = REPO_ROOT / "ColaData"


@pytest.fixture(autouse=True)
def _override_service():
    app.dependency_overrides[get_service] = lambda: VerificationService(
        extractor=Extractor(provider=FakeVisionProvider())
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class BrokenVisionProvider(VisionProvider):
    def extract(self, images):
        raise RuntimeError("vision backend unavailable")


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_verify_cola_real_record(client: TestClient):
    pdf = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()
    r = client.post("/api/verify/cola", files={"file": ("cola.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    # Parsed claimed fields come from the real record.
    assert body["claimed"]["brand_name"] == "BARENJAGER"
    assert body["claimed"]["source"] == "IMPORTED"
    assert len(body["images"]) == 2
    # Engine ran and timed itself.
    assert body["result"]["fields"], "expected per-field verdicts"
    assert isinstance(body["result"]["processing_ms"], int)
    assert body["provider"] == "FakeVisionProvider"


def test_verify_cola_rejects_empty_file(client: TestClient):
    r = client.post("/api/verify/cola", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r.status_code == 422


def test_verify_cola_rejects_garbage(client: TestClient):
    r = client.post("/api/verify/cola", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 422
    assert "COLA record" in r.json()["detail"]


def test_verify_cola_service_failure_returns_503(client: TestClient):
    app.dependency_overrides[get_service] = lambda: VerificationService(
        extractor=Extractor(provider=BrokenVisionProvider())
    )
    pdf = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()
    r = client.post("/api/verify/cola", files={"file": ("cola.pdf", pdf, "application/pdf")})
    assert r.status_code == 503
    assert "parsed" in r.json()["detail"]


def test_verify_manual_matching_passes(client: TestClient):
    # Claimed values aligned with the FakeVisionProvider's reading -> overall PASS.
    r = client.post(
        "/api/verify/manual",
        data={
            "brand_name": "OLD TOM DISTILLERY",
            "product_type": "distilled spirits",
            "source": "domestic",
            "net_contents": "750 MILLILITERS",
            "alcohol_content": "45",
            "class_type": "WHISKY",
            "producer": "Old Tom Distillery",
        },
        files={"images": ("label.png", b"fake-image-bytes", "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["result"]["overall"] == "PASS"


def test_verify_manual_requires_image(client: TestClient):
    r = client.post(
        "/api/verify/manual",
        data={"brand_name": "X"},
        files={"images": ("empty.png", b"", "image/png")},
    )
    assert r.status_code == 422


def test_verify_manual_service_failure_returns_503(client: TestClient):
    app.dependency_overrides[get_service] = lambda: VerificationService(
        extractor=Extractor(provider=BrokenVisionProvider())
    )
    r = client.post(
        "/api/verify/manual",
        data={"brand_name": "OLD TOM DISTILLERY"},
        files={"images": ("label.png", b"fake-image-bytes", "image/png")},
    )
    assert r.status_code == 503
    assert "could not be completed" in r.json()["detail"]


def test_verify_batch_mixed(client: TestClient):
    pdf1 = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()
    pdf2 = (COLA_DIR / "OMB No. 1512-0092.pdf").read_bytes()
    files = [
        ("files", ("a.pdf", pdf1, "application/pdf")),
        ("files", ("b.pdf", pdf2, "application/pdf")),
        ("files", ("bad.pdf", b"not a pdf", "application/pdf")),  # one bad file must not fail the batch
    ]
    r = client.post("/api/verify/batch", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total"] == 3
    assert body["summary"]["ERROR"] == 1  # the bad file
    items = {it["filename"]: it for it in body["items"]}
    assert items["a.pdf"]["brand_name"] == "BARENJAGER"
    assert items["a.pdf"]["result"]["overall"] in {"PASS", "FLAG", "FAIL"}
    assert items["a.pdf"]["counts"]["pass"] >= 1
    assert items["bad.pdf"]["error"] is not None
    assert items["bad.pdf"]["result"] is None


def test_verify_batch_service_failure_is_reported_as_error(client: TestClient):
    app.dependency_overrides[get_service] = lambda: VerificationService(
        extractor=Extractor(provider=BrokenVisionProvider())
    )
    pdf = (COLA_DIR / "OMB No. 1513-0020.pdf").read_bytes()
    r = client.post("/api/verify/batch", files=[("files", ("a.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["ERROR"] == 1
    assert body["items"][0]["overall"] == "ERROR"
    assert "parsed" in body["items"][0]["error"]
