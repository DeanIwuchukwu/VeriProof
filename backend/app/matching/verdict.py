"""Verdict models — the assistive output of the engine (SPEC F7).

Statuses are framed for human review: the tool flags, it never auto-approves or
auto-rejects. INFO/NOT_CHECKED never downgrade the overall result.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    PASS = "PASS"  # claim and label agree
    FLAG = "FLAG"  # discrepancy worth a human's eyes
    FAIL = "FAIL"  # clear violation / mismatch
    INFO = "INFO"  # advisory, no judgment (e.g. class/type)
    NOT_CHECKED = "NOT_CHECKED"  # nothing to compare against


# Severity ordering for rolling up the overall verdict.
_SEVERITY = {
    Status.FAIL: 4,
    Status.FLAG: 3,
    Status.PASS: 2,
    Status.INFO: 1,
    Status.NOT_CHECKED: 0,
}


class FieldVerdict(BaseModel):
    field: str
    label: str
    status: Status
    claimed: str | None = None
    extracted: str | None = None
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_image: int | None = None


class VerificationResult(BaseModel):
    fields: list[FieldVerdict] = Field(default_factory=list)
    overall: Status = Status.NOT_CHECKED
    image_quality: str = "good"
    processing_ms: int | None = None
    notes: str | None = None

    def compute_overall(self) -> Status:
        """FAIL if any FAIL; else FLAG if any FLAG; else PASS if anything passed."""
        if not self.fields:
            self.overall = Status.NOT_CHECKED
            return self.overall
        worst = max(self.fields, key=lambda f: _downgrade_rank(f.status))
        rank = _downgrade_rank(worst.status)
        if rank >= _downgrade_rank(Status.FAIL):
            self.overall = Status.FAIL
        elif rank >= _downgrade_rank(Status.FLAG):
            self.overall = Status.FLAG
        elif any(f.status == Status.PASS for f in self.fields):
            self.overall = Status.PASS
        else:
            self.overall = Status.NOT_CHECKED
        return self.overall


def _downgrade_rank(status: Status) -> int:
    # Only FAIL/FLAG/PASS participate in downgrade; INFO/NOT_CHECKED are neutral.
    return {Status.FAIL: 3, Status.FLAG: 2, Status.PASS: 1}.get(status, 0)
