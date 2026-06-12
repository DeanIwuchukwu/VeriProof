"""Normalization & parsing helpers for matching.

Pure functions, no I/O. These encode the "judgment" the engine needs: that
"STONE'S THROW" equals "Stone's Throw", that "35" equals "35% ALC./VOL.", and that
"750 MILLILITERS" equals "750ML" (SPEC §4).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_SMART_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalize_text(s: str | None) -> str:
    """Lowercase, unify quotes, drop punctuation, collapse whitespace."""
    if not s:
        return ""
    s = s.translate(_SMART_QUOTES).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a: str | None, b: str | None) -> float:
    """0..1 similarity of two strings after normalization."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def fuzzy_equal(a: str | None, b: str | None, threshold: float = 0.88) -> bool:
    """Lenient name match: equal-after-normalize, substring, or high similarity.

    Substring matching is token-aware so short tokens don't spuriously match
    ("ale" inside "table"): we require the shorter to be a whole-token subsequence
    of the longer, or a high overall ratio.
    """
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = na.split(), nb.split()
    short, long = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if _is_token_subsequence(short, long):
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def _is_token_subsequence(short: list[str], long: list[str]) -> bool:
    """True if all tokens of `short` appear in order within `long`."""
    it = iter(long)
    return all(tok in it for tok in short)


# ----- alcohol content ------------------------------------------------------

def parse_abv(s: str | None) -> float | None:
    """First percentage/number in an ABV string. '35% ALC./VOL.' -> 35.0."""
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?", s)
    return float(m.group(1)) if m else None


def parse_proof(s: str | None) -> float | None:
    """Proof value if present. '(90 Proof)' -> 90.0."""
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*proof", s, re.IGNORECASE)
    return float(m.group(1)) if m else None


# ----- net contents ---------------------------------------------------------

# canonical volume in millilitres for liquid units; gallons kept as their own class.
_UNIT_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "millilitre": 1.0,
    "millilitres": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "centiliters": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "litre": 1000.0,
    "litres": 1000.0,
}
_GALLON_UNITS = {"gal", "gallon", "gallons"}


def parse_net_contents(s: str | None) -> tuple[float, str] | None:
    """Parse a size into a comparable (value, unit_class).

    Returns (millilitres, 'ml') for liquid volumes, (gallons, 'gal') for kegs,
    or None if unparseable. Trailing notes like '(SAKE only)' are ignored.
    """
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z.]+)", s.strip())
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower().rstrip(".")
    if unit in _UNIT_TO_ML:
        return value * _UNIT_TO_ML[unit], "ml"
    if unit in _GALLON_UNITS:
        return value, "gal"
    return None


def net_contents_match(extracted: str | None, allowed: list[str], tol: float = 0.5) -> bool:
    """True if the label's net contents matches any of the form's allowed sizes."""
    e = parse_net_contents(extracted)
    if e is None:
        return False
    for cand in allowed:
        c = parse_net_contents(cand)
        if c and c[1] == e[1] and abs(c[0] - e[0]) <= tol:
            return True
    return False
