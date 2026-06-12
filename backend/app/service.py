"""Verification service — wires parsing, extraction, and matching into one call.

Stateless: it holds no per-request data and persists nothing (SPEC N4). The vision
provider is built lazily so the app starts even before a key is configured; a missing
key surfaces as a clean error on first use, not a crash at import.
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

    def verify_cola(self, pdf_bytes: bytes) -> tuple[ColaRecord, VerificationResult]:
        record = self._parser.parse(pdf_bytes)
        result = self._run(record.claimed, record.label_images)
        return record, result

    def verify_manual(
        self, claimed: ClaimedFields, images: list[LabelImage]
    ) -> VerificationResult:
        return self._run(claimed, images)

    def _run(self, claimed: ClaimedFields, images: list[LabelImage]) -> VerificationResult:
        start = time.perf_counter()
        extracted = self._get_extractor().extract(images)
        result = self._engine.verify(claimed, extracted)
        result.processing_ms = int((time.perf_counter() - start) * 1000)
        return result
