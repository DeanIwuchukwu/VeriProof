"""Verification service — wires parsing, extraction, and matching into one call.

The service itself holds no per-request state; persistence (verifications + reviewer
decisions, SPEC N4) happens at the API layer via app/db.py. The vision provider is
built lazily so the app starts even before a key is configured; a missing key
surfaces as a clean error on first use, not a crash at import.
"""

from __future__ import annotations

import time

from app.cola.models import ClaimedFields, ColaRecord, LabelImage
from app.cola.parser import ColaParser
from app.extraction.extractor import Extractor
from app.matching.engine import MatchEngine
from app.matching.verdict import VerificationResult


class VerificationService:
    def __init__(
        self,
        extractor: Extractor | None = None,
        engine: MatchEngine | None = None,
        parser: ColaParser | None = None,
    ):
        self._extractor = extractor
        self._engine = engine or MatchEngine()
        self._parser = parser or ColaParser()

    def _get_extractor(self) -> Extractor:
        if self._extractor is None:
            self._extractor = Extractor()  # builds the configured provider
        return self._extractor

    @property
    def provider_name(self) -> str:
        return self._get_extractor().provider_name

    def parse_cola(self, pdf_bytes: bytes) -> ColaRecord:
        return self._parser.parse(pdf_bytes)

    def verify_pdf(self, pdf_bytes: bytes) -> tuple[ColaRecord, VerificationResult]:
        """Full COLA-upload flow, timed end-to-end for the user-facing latency badge."""
        start = time.perf_counter()
        record = self.parse_cola(pdf_bytes)
        result = self.verify_record(record, started_at=start)
        return record, result

    def verify_cola(self, pdf_bytes: bytes) -> tuple[ColaRecord, VerificationResult]:
        return self.verify_pdf(pdf_bytes)

    def verify_record(
        self, record: ColaRecord, started_at: float | None = None
    ) -> VerificationResult:
        started_at = started_at if started_at is not None else time.perf_counter()
        result = self._run(record.claimed, record.label_images)
        result.processing_ms = self._elapsed_ms(started_at)
        return result

    def verify_manual(
        self, claimed: ClaimedFields, images: list[LabelImage]
    ) -> VerificationResult:
        start = time.perf_counter()
        result = self._run(claimed, images)
        result.processing_ms = self._elapsed_ms(start)
        return result

    def _run(self, claimed: ClaimedFields, images: list[LabelImage]) -> VerificationResult:
        extracted = self._get_extractor().extract(images)
        result = self._engine.verify(claimed, extracted)
        return result

    @staticmethod
    def _elapsed_ms(started_at: float | None) -> int:
        return int((time.perf_counter() - started_at) * 1000) if started_at is not None else 0
