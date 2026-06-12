"""ColaParser — extract claimed fields + label images from a TTB COLA record.

A COLA record (Form 5100.31, as exported from COLA Online) is a PDF whose first page
carries the application form and whose later pages carry the affixed label artwork.

Parsing strategy (see docs/SPEC.md §7 and the exploration that informed it):

* **Text fields** (brand, fanciful, net contents, ABV, class/type, applicant, DBA, …) —
  read from the PDF text layer, anchored on stable field *labels* (the field *numbers*
  vary across form versions, the labels do not).
* **Checkbox fields** (`TYPE OF PRODUCT`, `SOURCE OF PRODUCT`) — not present in the text
  layer; read from vector drawings. The checked option uniquely carries a dark-grey fill
  mark (≈0.46) positioned just left of its label word.
* **Label images** — every record has a fixed header graphic; the real labels appear in
  reading order *after* the ``AFFIX COMPLETE SET OF LABELS BELOW`` marker, each introduced
  by an ``Image Type:`` caption (front / back / other) that also gives its dimensions.

The parser records what it reliably finds and leaves the rest ``None`` / ``UNKNOWN`` rather
than guessing (an LLM fallback, out of scope for this module, can fill gaps — SPEC WBS 2.3).
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from .models import ClaimedFields, ColaRecord, LabelImage, ProductSource, ProductType

LABELS_MARKER = "AFFIX COMPLETE SET OF LABELS BELOW"
_USED_ON_LABEL = "(Used on label)"

# A line that opens a new numbered form field, e.g. "13. ALCOHOL CONTENT" or "8a. MAILING".
_FIELD_HEADER = re.compile(r"^\d{1,2}[a-z]?\.\s+\S")
# Qualifier lines that sit between a label and its value.
_SKIP_LINES = {"(Required)", "(If any)", ""}


def _open(source: bytes | str | Path) -> fitz.Document:
    if isinstance(source, bytes | bytearray):
        return fitz.open(stream=bytes(source), filetype="pdf")
    return fitz.open(str(source))


def _clean(text: str) -> str:
    return text.replace("\xa0", " ").strip()


class ColaParser:
    """Parse a COLA record PDF into a :class:`ColaRecord`."""

    def parse(self, source: bytes | str | Path) -> ColaRecord:
        doc = _open(source)
        try:
            page_texts = [doc[p].get_text() for p in range(doc.page_count)]
            full_text = "\n".join(page_texts)
            lines = [_clean(ln) for ln in full_text.splitlines()]

            claimed = self._parse_fields(doc, lines)
            images = self._extract_label_images(doc, full_text)
            return ColaRecord(
                claimed=claimed,
                label_images=images,
                form_version=self._form_version(full_text),
                raw_text=full_text,
            )
        finally:
            doc.close()

    # ----- text fields -------------------------------------------------------

    def _parse_fields(self, doc: fitz.Document, lines: list[str]) -> ClaimedFields:
        ttb_id = None
        if m := re.search(r"\b(\d{14})\b", "\n".join(lines)):
            ttb_id = m.group(1)

        applicant, dba = self._applicant_and_dba(lines)
        product_type, source = self._checkboxes(doc)

        return ClaimedFields(
            ttb_id=ttb_id,
            serial_number=self._value_after(lines, "SERIAL NUMBER"),
            brand_name=self._value_after(lines, "BRAND NAME"),
            fanciful_name=self._value_after(lines, "FANCIFUL NAME"),
            product_type=product_type,
            source=source,
            net_contents=self._net_contents(lines),
            alcohol_content=self._value_after(lines, "ALCOHOL CONTENT", numeric=True),
            class_type_description=self._value_after(lines, "CLASS/TYPE DESCRIPTION"),
            applicant_name_address=applicant,
            dba_tradename=dba,
            formula=self._value_after(lines, "FORMULA", numeric=True),
        )

    def _find(self, lines: list[str], label: str, start: int = 0) -> int:
        label = label.upper()
        for i in range(start, len(lines)):
            if label in lines[i].upper():
                return i
        return -1

    def _value_after(
        self, lines: list[str], label: str, *, numeric: bool = False
    ) -> str | None:
        """First real value line after a field label, skipping qualifier lines.

        Stops at the next numbered field header. When ``numeric`` is set, returns the
        first line containing a digit (ABV/formula values), so an adjacent empty field
        label is not mistaken for the value.
        """
        i = self._find(lines, label)
        if i < 0:
            return None
        for ln in lines[i + 1 :]:
            if ln in _SKIP_LINES:
                continue
            if _FIELD_HEADER.match(ln) or self._is_known_label(ln):
                return None
            if numeric and not any(c.isdigit() for c in ln):
                # skip adjacent label/empty lines until the numeric value appears
                continue
            return ln
        return None

    @staticmethod
    def _is_known_label(line: str) -> bool:
        up = line.upper()
        return any(
            kw in up
            for kw in (
                "BRAND NAME",
                "FANCIFUL NAME",
                "MAILING ADDRESS",
                "EMAIL ADDRESS",
                "NET CONTENTS",
                "ALCOHOL CONTENT",
                "TYPE OF PRODUCT",
                "SERIAL NUMBER",
                "WINE APPELLATION",
                "PHONE NUMBER",
                "EXPIRATION DATE",
                "GRAPE VARIETAL",
            )
        )

    def _net_contents(self, lines: list[str]) -> list[str]:
        i = self._find(lines, "NET CONTENTS")
        if i < 0:
            return []
        collected: list[str] = []
        for ln in lines[i + 1 :]:
            if ln in _SKIP_LINES:
                continue
            if _FIELD_HEADER.match(ln) or self._is_known_label(ln):
                break
            collected.append(ln)
        if not collected:
            return []
        joined = " ".join(collected)
        if "," in joined:
            return [p.strip() for p in joined.split(",") if p.strip()]
        return collected

    def _applicant_and_dba(self, lines: list[str]) -> tuple[str | None, str | None]:
        i = self._find(lines, "NAME AND ADDRESS OF APPLICANT")
        if i < 0:
            return None, None
        # The applicant label spans several lines, ending with "...USED ON LABEL ...".
        start = i
        for j in range(i, min(i + 6, len(lines))):
            if "USED ON LABEL" in lines[j].upper():
                start = j
                break
        collected: list[str] = []
        for ln in lines[start + 1 :]:
            if ln in _SKIP_LINES:
                continue
            if _FIELD_HEADER.match(ln) or self._is_known_label(ln):
                break
            collected.append(ln)
        dba = None
        kept: list[str] = []
        for ln in collected:
            if _USED_ON_LABEL.lower() in ln.lower():
                dba = ln.replace(_USED_ON_LABEL, "").strip()
            else:
                kept.append(ln)
        applicant = ", ".join(kept) if kept else None
        return applicant, dba

    # ----- checkboxes (vector drawings) -------------------------------------

    def _checkboxes(self, doc: fitz.Document) -> tuple[ProductType, ProductSource]:
        page = doc[0]
        checked = self._checked_options(
            page, {"WINE", "DISTILLED", "MALT", "Domestic", "Imported"}
        )
        if "DISTILLED" in checked:
            product_type = ProductType.DISTILLED_SPIRITS
        elif "MALT" in checked:
            product_type = ProductType.MALT_BEVERAGE
        elif "WINE" in checked:
            product_type = ProductType.WINE
        else:
            product_type = ProductType.UNKNOWN

        if "Imported" in checked:
            source = ProductSource.IMPORTED
        elif "Domestic" in checked:
            source = ProductSource.DOMESTIC
        else:
            source = ProductSource.UNKNOWN
        return product_type, source

    @staticmethod
    def _checked_options(page: fitz.Page, option_words: set[str]) -> set[str]:
        # A checked box carries a small dark-grey (≈0.46) fill mark; unchecked boxes
        # only have lighter grey (≈0.66) / white fills. Collect the dark marks.
        marks: list[fitz.Rect] = []
        for d in page.get_drawings():
            fill = d.get("fill")
            if not fill or len(fill) < 3:
                continue
            if all(0.40 <= c <= 0.52 for c in fill[:3]):
                r = d["rect"]
                if 3 <= r.width <= 12 and 3 <= r.height <= 12:
                    marks.append(r)

        checked: set[str] = set()
        for w in page.get_text("words"):
            word = w[4]
            if word not in option_words:
                continue
            wx0, wy0, _wx1, wy1 = w[0], w[1], w[2], w[3]
            for r in marks:
                cy = (r.y0 + r.y1) / 2
                if (
                    wy0 - 3 <= cy <= wy1 + 3
                    and r.x0 < wx0
                    and r.x1 <= wx0 + 3
                    and (wx0 - r.x0) <= 45
                ):
                    checked.add(word)
                    break
        return checked

    # ----- label images ------------------------------------------------------

    def _extract_label_images(
        self, doc: fitz.Document, full_text: str
    ) -> list[LabelImage]:
        marker_key: tuple[int, float] | None = None
        image_items: list[tuple[int, float, int]] = []
        for pno in range(doc.page_count):
            page = doc[pno]
            for r in page.search_for(LABELS_MARKER):
                k = (pno, float(r.y0))
                if marker_key is None or k < marker_key:
                    marker_key = k
            for inf in page.get_image_info(xrefs=True):
                xref = inf.get("xref", 0)
                if xref:
                    image_items.append((pno, float(fitz.Rect(inf["bbox"]).y0), xref))

        if marker_key is None:
            return []  # no label section found

        image_items.sort()
        labels = [it for it in image_items if (it[0], it[1]) > marker_key]
        captions = self._caption_types(full_text)

        result: list[LabelImage] = []
        for idx, (pno, _y0, xref) in enumerate(labels):
            try:
                info = doc.extract_image(xref)
            except Exception:  # noqa: BLE001 — skip an unreadable image, keep the rest
                continue
            image_type, dims = captions[idx] if idx < len(captions) else (None, None)
            result.append(
                LabelImage(
                    image_type=image_type,
                    actual_dimensions=dims,
                    width_px=info.get("width", 0),
                    height_px=info.get("height", 0),
                    image_format=info.get("ext", "png"),
                    page_index=pno,
                    data=info.get("image", b""),
                )
            )
        return result

    @staticmethod
    def _caption_types(full_text: str) -> list[tuple[str | None, str | None]]:
        lines = [_clean(ln) for ln in full_text.splitlines()]
        out: list[tuple[str | None, str | None]] = []
        i = 0
        while i < len(lines):
            if lines[i].rstrip(":").strip().upper() == "IMAGE TYPE":
                image_type = None
                dims = None
                for ln in lines[i + 1 : i + 6]:
                    if ln.upper().startswith("ACTUAL DIMENSIONS"):
                        dims = ln.split(":", 1)[1].strip() if ":" in ln else None
                        break
                    if ln and image_type is None and not ln.upper().startswith("NOTE:"):
                        image_type = ln
                out.append((image_type, dims))
            i += 1
        return out

    @staticmethod
    def _form_version(full_text: str) -> str | None:
        matches = re.findall(r"TTB F 5100\.31\s*\(([^)]+)\)", full_text)
        return f"TTB F 5100.31 ({matches[-1]})" if matches else None
