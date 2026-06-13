"""Ephemeral history-page chat over saved verifications and shortlisted PDFs."""

from __future__ import annotations

import base64
import re
from functools import lru_cache
from typing import Any

import fitz
from openai import OpenAI
from pydantic import BaseModel, Field

from app import db
from app.cola.parser import ColaParser
from app.config import Settings, get_settings
from app.extraction.tls import use_system_trust_store


class HistoryVisibleItem(BaseModel):
    verification_id: str
    created_at: str | None = None
    source: str
    filename: str | None = None
    ttb_id: str | None = None
    brand_name: str | None = None
    product_type: str | None = None
    overall: str
    processing_ms: int | None = None
    has_pdf: bool
    decision: dict | None = None


class HistoryChatTurn(BaseModel):
    role: str
    content: str


class HistoryChatRequest(BaseModel):
    message: str
    open_verification_id: str | None = None
    visible_items: list[HistoryVisibleItem] = Field(default_factory=list)
    recent_turns: list[HistoryChatTurn] = Field(default_factory=list)


class HistoryChatCitation(BaseModel):
    verification_id: str
    filename: str | None = None
    ttb_id: str | None = None
    page: int | None = None
    source: str


class HistoryChatResponse(BaseModel):
    answer: str
    citations: list[HistoryChatCitation] = Field(default_factory=list)
    pdf_used: bool = False


_PDF_KEYWORDS = {
    "pdf", "page", "pages", "applicant", "importer", "warning", "label", "printed",
    "says", "exact", "wording", "where", "front", "back", "text", "line",
    "fax", "phone", "telephone", "tel", "contact", "number",
}
_IMAGE_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
_FIELD_ALIAS_ORDER = (
    ("fax_number", ("fax number", "fax", "facsimile")),
    ("phone_number", ("phone number", "telephone number", "telephone", "phone", "contact number", "tel")),
    ("email_address", ("email address", "email", "e-mail")),
    ("serial_number", ("serial number", "serial no", "serial")),
    ("formula", ("formula number", "formula")),
    ("ttb_id", ("ttb id", "ttb number", "cola id", "id number")),
    ("applicant_name_address", ("applicant name", "applicant address", "name and address", "applicant")),
    ("brand_name", ("brand name", "brand")),
    ("fanciful_name", ("fanciful name", "fanciful")),
    ("alcohol_content", ("alcohol content", "abv", "alcohol by volume", "alcohol")),
    ("net_contents", ("net contents", "net content", "contents", "bottle size", "size")),
)
_FORM_FIELD_HEADERS = re.compile(r"^\d{1,2}[a-z]?\.\s+\S")
_FORM_SKIP_LINES = {"(Required)", "(If any)", "(Wine Only)", "", "N/A"}
_KNOWN_FORM_LABELS = (
    "TTB ID",
    "SERIAL NUMBER",
    "SOURCE OF PRODUCT",
    "TYPE OF PRODUCT",
    "NAME AND ADDRESS OF APPLICANT",
    "BRAND NAME",
    "FANCIFUL NAME",
    "MAILING ADDRESS",
    "EMAIL ADDRESS",
    "GRAPE VARIETAL",
    "FORMULA",
    "NET CONTENTS",
    "ALCOHOL CONTENT",
    "WINE APPELLATION",
    "PHONE NUMBER",
    "FAX NUMBER",
)
_NUMERIC_FIELDS = {"formula", "ttb_id"}
_LINE_FIELDS = {
    "fax_number": "FAX NUMBER",
    "phone_number": "PHONE NUMBER",
    "email_address": "EMAIL ADDRESS",
    "serial_number": "SERIAL NUMBER",
    "formula": "FORMULA",
    "brand_name": "BRAND NAME",
    "fanciful_name": "FANCIFUL NAME",
    "alcohol_content": "ALCOHOL CONTENT",
}
_DISPLAY_LABELS = {
    "fax_number": "fax number",
    "phone_number": "phone number",
    "email_address": "email address",
    "serial_number": "serial number",
    "formula": "formula number",
    "ttb_id": "TTB ID",
    "applicant_name_address": "applicant name/address",
    "brand_name": "brand name",
    "fanciful_name": "fanciful name",
    "alcohol_content": "alcohol content",
    "net_contents": "net contents",
}


class HistoryChatService:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. History chat requires the OpenAI provider to be configured."
            )
        use_system_trust_store()
        self._client = OpenAI(
            api_key=self._settings.openai_api_key,
            timeout=self._settings.request_timeout,
            max_retries=self._settings.max_retries,
        )
        self._parser = ColaParser()

    def answer(self, req: HistoryChatRequest) -> HistoryChatResponse:
        message = (req.message or "").strip()
        if not message:
            raise ValueError("Please enter a question for the history assistant.")

        candidates = self._rank_visible_items(message, req.visible_items, req.open_verification_id)
        details = [db.get_verification(it.verification_id) for it in candidates]
        details = [d for d in details if d is not None]

        pdf_used = False
        citations: list[HistoryChatCitation] = []
        content: list[dict] = []

        content.append({"type": "input_text", "text": self._render_text_context(req, candidates, details)})

        exact_lookup = _lookup_exact_field(message, details)
        if exact_lookup is not None:
            pdf_used = exact_lookup["inspected_pdf"]
            content.append({"type": "input_text", "text": _render_exact_lookup_context(exact_lookup)})
            citations.extend(exact_lookup["citations"])

        if self._needs_pdf(message):
            for detail in details[:2]:
                if exact_lookup is not None and detail["verification_id"] in exact_lookup["searched_ids"]:
                    continue
                pdf = db.get_pdf(detail["verification_id"])
                if pdf is None:
                    continue
                pdf_used = True
                pdf_bytes, _ = pdf
                pdf_ctx = self._pdf_context(detail, pdf_bytes, message)
                if pdf_ctx["text"]:
                    content.append({"type": "input_text", "text": pdf_ctx["text"]})
                for image in pdf_ctx["images"]:
                    content.append(image)
                citations.extend(pdf_ctx["citations"])

        if not citations:
            citations = [
                HistoryChatCitation(
                    verification_id=d["verification_id"],
                    filename=d.get("filename"),
                    ttb_id=d.get("ttb_id"),
                    source="history",
                )
                for d in details[:3]
            ]

        response = self._client.responses.create(
            model=self._settings.vision_model,
            input=[
                {"role": "system", "content": HISTORY_CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_output_tokens=min(self._settings.vision_max_tokens, 900),
        )
        answer = (response.output_text or "").strip()
        if not answer:
            answer = "I couldn't form a grounded answer from the saved history context."
        return HistoryChatResponse(answer=answer, citations=citations, pdf_used=pdf_used)

    def _rank_visible_items(
        self,
        message: str,
        items: list[HistoryVisibleItem],
        open_verification_id: str | None,
    ) -> list[HistoryVisibleItem]:
        if not items:
            return []
        query_tokens = _tokens(message)
        scored: list[tuple[float, HistoryVisibleItem]] = []
        for item in items:
            score = 0.0
            if item.verification_id == open_verification_id:
                score += 6.0
            score += _score_text(item.filename, query_tokens, 3.0)
            score += _score_text(item.ttb_id, query_tokens, 4.0)
            score += _score_text(item.brand_name, query_tokens, 4.0)
            score += _score_text(item.product_type, query_tokens, 1.5)
            score += _score_text(item.overall, query_tokens, 1.0)
            if item.decision:
                score += _score_text(item.decision.get("action"), query_tokens, 1.0)
                score += _score_text(item.decision.get("note"), query_tokens, 2.0)
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [item for score, item in scored if score > 0][:5]
        if open_verification_id and all(it.verification_id != open_verification_id for it in top):
            selected = next((it for it in items if it.verification_id == open_verification_id), None)
            if selected:
                top.insert(0, selected)
        return top or items[:3]

    def _render_text_context(
        self,
        req: HistoryChatRequest,
        candidates: list[HistoryVisibleItem],
        details: list[dict],
    ) -> str:
        turns = "\n".join(
            f"{'User' if t.role == 'user' else 'Assistant'}: {t.content.strip()}"
            for t in req.recent_turns[-6:]
            if t.content.strip()
        )
        visible = "\n".join(
            f"- {it.filename or it.verification_id} | brand={it.brand_name or 'n/a'} | ttb_id={it.ttb_id or 'n/a'} "
            f"| result={it.overall} | decision={it.decision.get('action') if it.decision else 'none'}"
            for it in req.visible_items[:50]
        )
        detailed = "\n\n".join(_detail_block(d) for d in details[:5])
        return (
            f"User question:\n{req.message}\n\n"
            f"Current open verification id: {req.open_verification_id or 'none'}\n\n"
            f"Recent chat turns:\n{turns or 'None'}\n\n"
            f"Visible history summaries:\n{visible or 'None'}\n\n"
            f"Shortlisted verification details:\n{detailed or 'None'}"
        )

    def _pdf_context(self, detail: dict, pdf_bytes: bytes, message: str) -> dict:
        citations: list[HistoryChatCitation] = []
        text_blocks: list[str] = []
        image_blocks: list[dict] = []

        excerpts = _extract_pdf_text_excerpts(pdf_bytes, message, limit=2)
        if excerpts:
            joined = "\n\n".join(
                f"PDF text excerpt from {detail.get('filename') or detail['verification_id']} page {page}:\n{snippet}"
                for page, snippet in excerpts
            )
            text_blocks.append(joined)
            citations.extend(
                HistoryChatCitation(
                    verification_id=detail["verification_id"],
                    filename=detail.get("filename"),
                    ttb_id=detail.get("ttb_id"),
                    page=page,
                    source="pdf_text",
                )
                for page, _ in excerpts
            )

        try:
            record = self._parser.parse(pdf_bytes)
        except Exception:
            record = None
        if record is not None:
            for im in record.label_images[:2]:
                mime = _IMAGE_MIME.get((im.image_format or "").lower(), "image/jpeg")
                image_blocks.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{base64.standard_b64encode(im.data).decode('ascii')}",
                        "detail": "high",
                    }
                )
            if record.label_images:
                text_blocks.append(
                    f"Label images attached from {detail.get('filename') or detail['verification_id']} "
                    f"({len(record.label_images)} image(s), first {min(2, len(record.label_images))} shared)."
                )
                citations.append(
                    HistoryChatCitation(
                        verification_id=detail["verification_id"],
                        filename=detail.get("filename"),
                        ttb_id=detail.get("ttb_id"),
                        source="label_image",
                    )
                )

        return {"text": "\n\n".join(text_blocks), "images": image_blocks, "citations": citations}

    @staticmethod
    def _needs_pdf(message: str) -> bool:
        if _detect_exact_field(message) is not None:
            return False
        tokens = _tokens(message)
        return any(tok in _PDF_KEYWORDS for tok in tokens)


def _detail_block(detail: dict) -> str:
    fields = detail.get("result", {}).get("fields", []) if detail.get("result") else []
    field_lines = "\n".join(
        f"  - {f.get('label')}: status={f.get('status')} claimed={f.get('claimed')} extracted={f.get('extracted')} reason={f.get('reason')}"
        for f in fields[:8]
    )
    decisions = detail.get("decisions", [])
    decision_lines = "\n".join(
        f"  - {d.get('action')} @ {d.get('created_at')}: {d.get('note') or ''}" for d in decisions[-3:]
    )
    claimed = detail.get("claimed") or {}
    return (
        f"Record: {detail.get('filename') or detail.get('ttb_id') or detail.get('verification_id')}\n"
        f"TTB ID: {detail.get('ttb_id') or 'n/a'} | Brand: {detail.get('brand_name') or 'n/a'} | "
        f"Overall: {detail.get('overall')} | Has PDF: {detail.get('has_pdf')}\n"
        f"Claimed: brand={claimed.get('brand_name')}, product_type={claimed.get('product_type')}, "
        f"source={claimed.get('source')}, applicant={claimed.get('applicant_name_address')}\n"
        f"Field verdicts:\n{field_lines or '  - none'}\n"
        f"Decisions:\n{decision_lines or '  - none'}"
    )


def _render_exact_lookup_context(result: dict[str, Any]) -> str:
    record = result.get("record") or "the shortlisted PDF"
    field_key = result["field"]
    field_label = _DISPLAY_LABELS.get(field_key, field_key.replace("_", " "))
    page = result.get("page")
    snippet = result.get("snippet") or "None"
    value = result.get("value")
    return (
        "Deterministic field lookup:\n"
        f"- Requested field: {field_label}\n"
        f"- Record searched first: {record}\n"
        f"- Result: {'FOUND' if value else 'NOT FOUND'}\n"
        f"- Value: {value or 'not found in the supplied PDF evidence'}\n"
        f"- Page: {page or 'n/a'}\n"
        f"- Evidence snippet: {snippet}\n"
        "Use this exact lookup as ground truth for the field value. "
        "Lead with the direct answer, then give a short evidence section if helpful."
    )


def _extract_pdf_text_excerpts(pdf_bytes: bytes, message: str, limit: int = 2) -> list[tuple[int, str]]:
    query_tokens = _tokens(message)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[tuple[float, int, str]] = []
    try:
        for idx, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text:
                continue
            score = _score_text(text, query_tokens, 1.0)
            pages.append((score, idx + 1, _best_snippet(text, query_tokens)))
    finally:
        doc.close()
    pages.sort(key=lambda row: row[0], reverse=True)
    picked = [(page_no, snippet) for score, page_no, snippet in pages if score > 0][:limit]
    if picked:
        return picked
    fallback = pages[:1]
    return [(page_no, snippet) for _, page_no, snippet in fallback]


def _best_snippet(text: str, query_tokens: set[str]) -> str:
    compact = " ".join(text.split())
    lowered = compact.lower()
    for tok in sorted(query_tokens, key=len, reverse=True):
        idx = lowered.find(tok)
        if idx >= 0:
            start = max(0, idx - 220)
            end = min(len(compact), idx + 580)
            return compact[start:end]
    return compact[:800]


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) >= 2}


def _score_text(text: str | None, tokens: set[str], weight: float) -> float:
    if not text or not tokens:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for tok in tokens if tok in lowered)
    return hits * weight


def _detect_exact_field(message: str) -> str | None:
    lowered = (message or "").lower()
    for field_name, aliases in _FIELD_ALIAS_ORDER:
        if any(alias in lowered for alias in aliases):
            return field_name
    return None


def _lookup_exact_field(message: str, details: list[dict]) -> dict[str, Any] | None:
    field_name = _detect_exact_field(message)
    if field_name is None:
        return None

    searched_ids: list[str] = []
    citations: list[HistoryChatCitation] = []
    for detail in details[:3]:
        verification_id = detail["verification_id"]
        pdf = db.get_pdf(verification_id)
        if pdf is None:
            continue
        searched_ids.append(verification_id)
        pdf_bytes, _ = pdf
        match = _extract_exact_field_from_pdf(pdf_bytes, field_name)
        if match is None:
            continue
        citations.append(
            HistoryChatCitation(
                verification_id=verification_id,
                filename=detail.get("filename"),
                ttb_id=detail.get("ttb_id"),
                page=match.get("page"),
                source="pdf_text",
            )
        )
        return {
            "field": field_name,
            "value": match.get("value"),
            "page": match.get("page"),
            "snippet": match.get("snippet"),
            "record": detail.get("filename") or detail.get("brand_name") or detail.get("ttb_id"),
            "citations": citations,
            "inspected_pdf": True,
            "searched_ids": searched_ids,
        }

    return {
        "field": field_name,
        "value": None,
        "page": None,
        "snippet": None,
        "record": details[0].get("filename") if details else None,
        "citations": citations,
        "inspected_pdf": bool(searched_ids),
        "searched_ids": searched_ids,
    }


def _extract_exact_field_from_pdf(pdf_bytes: bytes, field_name: str) -> dict[str, Any] | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for idx, page in enumerate(doc):
            lines = _page_lines(page)
            if not lines:
                continue
            match = _extract_exact_field_from_lines(lines, field_name)
            if match is None:
                continue
            match["page"] = idx + 1
            if match.get("value"):
                match["snippet"] = _snippet_for_value(lines, match.get("label"), match["value"])
            else:
                match["snippet"] = _snippet_for_label(lines, match.get("label"))
            return match
    finally:
        doc.close()
    return None


def _extract_exact_field_from_lines(lines: list[str], field_name: str) -> dict[str, Any] | None:
    if field_name == "ttb_id":
        return _extract_ttb_id(lines)
    if field_name == "applicant_name_address":
        return _extract_applicant(lines)
    if field_name == "net_contents":
        return _extract_net_contents(lines)
    label = _LINE_FIELDS.get(field_name)
    if label:
        value = _value_after_label(lines, label, numeric=field_name in _NUMERIC_FIELDS)
        return {"label": label, "value": value}
    return None


def _extract_ttb_id(lines: list[str]) -> dict[str, Any] | None:
    for i, line in enumerate(lines):
        if "TTB ID" not in line.upper():
            continue
        for candidate in lines[i:i + 4]:
            if match := re.search(r"\b(\d{14})\b", candidate):
                return {"label": "TTB ID", "value": match.group(1)}
    for line in lines:
        if match := re.search(r"\b(\d{14})\b", line):
            return {"label": "TTB ID", "value": match.group(1)}
    return None


def _extract_applicant(lines: list[str]) -> dict[str, Any] | None:
    label = "NAME AND ADDRESS OF APPLICANT"
    i = _find_label_index(lines, label)
    if i < 0:
        return None
    start = i
    for j in range(i, min(i + 8, len(lines))):
        if "USED ON LABEL" in lines[j].upper():
            start = j
            break
    collected: list[str] = []
    for line in lines[start + 1:]:
        if line in _FORM_SKIP_LINES:
            continue
        if _is_new_field(line):
            break
        collected.append(line)
    value = ", ".join(collected).strip() or None
    return {"label": label, "value": value}


def _extract_net_contents(lines: list[str]) -> dict[str, Any] | None:
    label = "NET CONTENTS"
    i = _find_label_index(lines, label)
    if i < 0:
        return None
    collected: list[str] = []
    for line in lines[i + 1:]:
        if line in _FORM_SKIP_LINES:
            continue
        if _is_new_field(line):
            break
        collected.append(line)
    value = ", ".join(collected).strip() or None
    return {"label": label, "value": value}


def _value_after_label(lines: list[str], label: str, *, numeric: bool = False) -> str | None:
    i = _find_label_index(lines, label)
    if i < 0:
        return None
    for line in lines[i + 1:]:
        if line in _FORM_SKIP_LINES:
            continue
        if _is_new_field(line):
            return None
        if numeric and not any(ch.isdigit() for ch in line):
            continue
        return line
    return None


def _find_label_index(lines: list[str], label: str) -> int:
    target = label.upper()
    for i, line in enumerate(lines):
        if target in line.upper():
            return i
    return -1


def _is_new_field(line: str) -> bool:
    upper = line.upper()
    return bool(_FORM_FIELD_HEADERS.match(line)) or any(header in upper for header in _KNOWN_FORM_LABELS)


def _page_lines(page: fitz.Page) -> list[str]:
    return [_normalize_line(line) for line in page.get_text("text").splitlines() if _normalize_line(line)]


def _normalize_line(line: str) -> str:
    return line.replace("\xa0", " ").strip()


def _snippet_for_value(lines: list[str], label: str | None, value: str) -> str:
    digits_only = re.sub(r"\D", "", value)
    if len(digits_only) <= 2:
        return _snippet_for_label(lines, label)
    upper_value = value.upper()
    for i, line in enumerate(lines):
        if upper_value in line.upper():
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            return " | ".join(lines[start:end])
    return _snippet_for_label(lines, label)


def _snippet_for_label(lines: list[str], label: str | None) -> str:
    if label:
        idx = _find_label_index(lines, label)
        if idx >= 0:
            end = min(len(lines), idx + 4)
            return " | ".join(lines[idx:end])
    return " | ".join(lines[:4]) if lines else ""


HISTORY_CHAT_SYSTEM_PROMPT = (
    "You are a history-page assistant for a TTB label-verification tool. "
    "Answer only from the supplied history summaries, verification details, PDF excerpts, and label images. "
    "If the evidence is incomplete, say so plainly. Distinguish between saved verification results and raw PDF evidence. "
    "Be concise and reviewer-friendly. Start with a direct answer in one sentence. "
    "Then, if useful, add a short 'Evidence:' section with only the most relevant facts. "
    "Prefer filenames, brands, and 'latest saved run' wording over internal verification ids. "
    "Do not surface verification ids unless the user explicitly asks for technical identifiers. "
    "When multiple saved runs disagree, summarize that briefly instead of dumping every run."
)


@lru_cache
def get_history_chat_service() -> HistoryChatService:
    return HistoryChatService()
