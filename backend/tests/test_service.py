"""VerificationService timing semantics."""

from __future__ import annotations

from app.cola.models import ClaimedFields, ColaRecord, LabelImage
from app.extraction.schema import ExtractedLabel
from app.matching.verdict import FieldVerdict, Status, VerificationResult
from app.service import VerificationService


class StubParser:
    def __init__(self, record: ColaRecord):
        self._record = record

    def parse(self, pdf_bytes: bytes) -> ColaRecord:
        return self._record


class StubExtractor:
    provider_name = "StubExtractor"

    def extract(self, images: list[LabelImage]) -> ExtractedLabel:
        return ExtractedLabel()


class StubEngine:
    def verify(self, claimed: ClaimedFields, extracted: ExtractedLabel) -> VerificationResult:
        return VerificationResult(
            fields=[FieldVerdict(field="brand_name", label="Brand Name", status=Status.PASS)]
        )


def test_verify_pdf_times_parse_plus_verification(monkeypatch):
    record = ColaRecord(claimed=ClaimedFields(brand_name="X"), label_images=[LabelImage(data=b"x")])
    service = VerificationService(
        extractor=StubExtractor(),
        engine=StubEngine(),
        parser=StubParser(record),
    )
    ticks = iter([100.0, 104.25])
    monkeypatch.setattr("app.service.time.perf_counter", lambda: next(ticks))

    parsed, result = service.verify_pdf(b"%PDF")

    assert parsed is record
    assert result.processing_ms == 4250


def test_verify_manual_keeps_timing_for_manual_flow(monkeypatch):
    service = VerificationService(
        extractor=StubExtractor(),
        engine=StubEngine(),
        parser=StubParser(ColaRecord(claimed=ClaimedFields(), label_images=[])),
    )
    ticks = iter([10.0, 12.5])
    monkeypatch.setattr("app.service.time.perf_counter", lambda: next(ticks))

    result = service.verify_manual(ClaimedFields(brand_name="X"), [LabelImage(data=b"x")])

    assert result.processing_ms == 2500
