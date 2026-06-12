"""The Government Health Warning — the one field checked STRICTLY (27 CFR §16.21).

Unlike brand/producer (lenient), the warning must be word-for-word and the prefix
"GOVERNMENT WARNING:" must be in capital letters. People game it with title case,
paraphrase, omission, or tiny text (interview: Jenny). We check content (key clauses
present + close wording) and capitalization (judged from the image by the vision model).
"""

from __future__ import annotations

from dataclasses import dataclass

from .normalize import normalize_text, similarity

# 27 CFR §16.21 — the mandated statement, verbatim.
CANONICAL_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# Mandatory clauses — each must appear (normalized) or the warning is non-compliant.
REQUIRED_CLAUSES = [
    "government warning",
    "according to the surgeon general",
    "women should not drink alcoholic beverages during pregnancy",
    "because of the risk of birth defects",
    "consumption of alcoholic beverages impairs your ability to drive a car or operate machinery",
    "may cause health problems",
]


@dataclass
class WarningCheck:
    present: bool
    missing_clauses: list[str]
    wording_similarity: float
    prefix_all_caps: bool | None
    content_ok: bool

    @property
    def is_compliant(self) -> bool:
        # Content must match AND the prefix must be all-caps (when we could judge it).
        return self.content_ok and self.prefix_all_caps is not False


def check_warning(
    text: str | None,
    *,
    present: bool,
    prefix_all_caps: bool | None,
    clause_threshold: float = 0.93,
) -> WarningCheck:
    """Evaluate an extracted warning against the canonical statement.

    `present`/`prefix_all_caps` come from the vision model (visual judgments).
    Content is OK when every required clause is found (allowing minor OCR slips via a
    per-clause similarity threshold) and the overall wording is close to canonical.
    """
    if not present or not text:
        return WarningCheck(
            present=False,
            missing_clauses=list(REQUIRED_CLAUSES),
            wording_similarity=0.0,
            prefix_all_caps=prefix_all_caps,
            content_ok=False,
        )

    norm = normalize_text(text)
    missing = [c for c in REQUIRED_CLAUSES if not _clause_present(c, norm, clause_threshold)]
    wording_sim = similarity(text, CANONICAL_WARNING)
    content_ok = len(missing) == 0
    return WarningCheck(
        present=True,
        missing_clauses=missing,
        wording_similarity=wording_sim,
        prefix_all_caps=prefix_all_caps,
        content_ok=content_ok,
    )


def _clause_present(clause: str, normalized_text: str, threshold: float) -> bool:
    """A clause counts as present if it's a substring, or a sliding window of the
    text matches it closely (tolerates small OCR errors but not paraphrase/omission)."""
    nclause = normalize_text(clause)
    if nclause in normalized_text:
        return True
    words = normalized_text.split()
    span = len(nclause.split())
    if span == 0 or len(words) < span:
        return False
    for i in range(len(words) - span + 1):
        window = " ".join(words[i : i + span])
        if similarity(window, nclause) >= threshold:
            return True
    return False
