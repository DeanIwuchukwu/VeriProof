"""Persistence layer — verifications (incl. the original COLA PDF) and reviewer decisions.

PostgreSQL in deployment (Railway injects DATABASE_URL); the tests bind an in-memory
SQLite engine via `use_engine`. When DATABASE_URL is unset the app still runs and
verifies — persistence is simply disabled (verification_id comes back null), mirroring
the lazy-provider philosophy in `service.py`.

Decisions are append-only: re-deciding adds a new row; the latest row wins for display.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    or_,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.cola.models import ColaRecord
from app.config import get_settings
from app.matching.verdict import VerificationResult

log = logging.getLogger("ttb.db")

DECISION_ACTIONS = ("ACCEPT", "REJECT")


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source: Mapped[str] = mapped_column(String(10))  # upload | manual | batch
    filename: Mapped[str | None] = mapped_column(Text, default=None)
    ttb_id: Mapped[str | None] = mapped_column(Text, default=None)
    brand_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type: Mapped[str | None] = mapped_column(Text, default=None)
    overall: Mapped[str] = mapped_column(String(12))
    processing_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    claimed: Mapped[dict | None] = mapped_column(JSON, default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    form_version: Mapped[str | None] = mapped_column(Text, default=None)
    # The original uploaded COLA PDF (None for manual entries) — label images are
    # re-derivable from it, so they are not stored separately.
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    pdf_size: Mapped[int | None] = mapped_column(Integer, default=None)
    # SHA-256 of the uploaded PDF — lets repeat uploads of the same file be linked.
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), default=None, index=True)

    decisions: Mapped[list[Decision]] = relationship(
        back_populates="verification", order_by="Decision.id", cascade="all, delete-orphan"
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verification_id: Mapped[str] = mapped_column(
        ForeignKey("verifications.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(6))  # ACCEPT | REJECT
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    verification: Mapped[Verification] = relationship(back_populates="decisions")


# ----- engine management ------------------------------------------------------

_SessionLocal: sessionmaker | None = None


def _normalize(url: str) -> str:
    """Map Railway/Heroku-style schemes onto the psycopg3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def init_db() -> bool:
    """Create the engine and tables from DATABASE_URL. Returns True when enabled."""
    url = get_settings().database_url
    if not url:
        log.warning("DATABASE_URL is not set — persistence disabled; verifications will not be saved.")
        return False
    try:
        engine = create_engine(_normalize(url), pool_pre_ping=True)
        use_engine(engine)
        return True
    except Exception:  # noqa: BLE001 — a bad DB must not stop verification service
        log.exception("Could not initialize the database — persistence disabled.")
        return False


def use_engine(engine: Engine) -> None:
    """Bind an explicit engine (also used by the tests with in-memory SQLite)."""
    global _SessionLocal
    Base.metadata.create_all(engine)
    # Minimal forward migration for tables created before pdf_sha256 existed
    # (create_all never alters existing tables; Alembic is out of scope).
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE verifications ADD COLUMN IF NOT EXISTS pdf_sha256 VARCHAR(64)"))
    except Exception:  # noqa: BLE001 — SQLite (fresh per test run) doesn't support IF NOT EXISTS
        pass
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def reset() -> None:
    """Detach the engine (tests)."""
    global _SessionLocal
    _SessionLocal = None


def enabled() -> bool:
    return _SessionLocal is not None


# ----- operations (each returns plain JSON-ready data; None signals 'not found') ----

def save_verification(
    *,
    source: str,
    result: VerificationResult,
    record: ColaRecord | None = None,
    claimed=None,
    filename: str | None = None,
    pdf: bytes | None = None,
) -> str | None:
    """Persist one verification; returns its id, or None when disabled/failed.

    Best-effort by design: a storage failure must never fail the verification itself.
    """
    if _SessionLocal is None:
        return None
    claimed = claimed if claimed is not None else (record.claimed if record else None)
    try:
        with _SessionLocal() as s, s.begin():
            v = Verification(
                source=source,
                filename=filename,
                ttb_id=claimed.ttb_id if claimed else None,
                brand_name=claimed.brand_name if claimed else None,
                product_type=claimed.product_type.value if claimed else None,
                overall=result.overall.value,
                processing_ms=result.processing_ms,
                claimed=claimed.model_dump(mode="json") if claimed else None,
                result=result.model_dump(mode="json"),
                form_version=record.form_version if record else None,
                pdf_data=pdf,
                pdf_size=len(pdf) if pdf else None,
                pdf_sha256=hashlib.sha256(pdf).hexdigest() if pdf else None,
            )
            s.add(v)
            s.flush()
            return v.id
    except Exception:  # noqa: BLE001
        log.exception("Failed to save verification")
        return None


def add_decision(verification_id: str, action: str, note: str | None) -> dict | None:
    """Append a reviewer decision; returns the saved row, or None if the id is unknown."""
    if _SessionLocal is None:
        return None
    with _SessionLocal() as s, s.begin():
        if s.get(Verification, verification_id) is None:
            return None
        d = Decision(verification_id=verification_id, action=action, note=note)
        s.add(d)
        s.flush()
        return _decision_dict(d)


def get_verification(verification_id: str) -> dict | None:
    """Full record (claimed, result, decisions) without the PDF bytes."""
    if _SessionLocal is None:
        return None
    with _SessionLocal() as s:
        v = s.get(Verification, verification_id)
        if v is None:
            return None
        return {
            **_summary_dict(v),
            "claimed": v.claimed,
            "result": v.result,
            "form_version": v.form_version,
            "decisions": [_decision_dict(d) for d in v.decisions],
        }


def get_pdf(verification_id: str) -> tuple[bytes, str | None] | None:
    """The stored original PDF, or None when absent (manual entries / unknown id)."""
    if _SessionLocal is None:
        return None
    with _SessionLocal() as s:
        v = s.get(Verification, verification_id)
        if v is None or not v.pdf_data:
            return None
        return v.pdf_data, v.filename


def delete_verification(verification_id: str) -> bool:
    """Hard-delete a saved verification (its decisions cascade). True if it existed."""
    if _SessionLocal is None:
        return False
    with _SessionLocal() as s, s.begin():
        v = s.get(Verification, verification_id)
        if v is None:
            return False
        s.delete(v)
        return True


def find_prior(ttb_id: str | None, pdf_sha256: str | None, limit: int = 5) -> list[dict]:
    """Earlier verifications of the same record — matched by TTB ID or exact file hash.

    Called BEFORE the new run is saved, so it never matches itself. Newest first,
    each with its latest decision; used to tell the reviewer "previously verified".
    """
    if _SessionLocal is None or not (ttb_id or pdf_sha256):
        return []
    conds = []
    if ttb_id:
        conds.append(Verification.ttb_id == ttb_id)
    if pdf_sha256:
        conds.append(Verification.pdf_sha256 == pdf_sha256)
    with _SessionLocal() as s:
        rows = s.execute(
            select(Verification).where(or_(*conds)).order_by(Verification.created_at.desc()).limit(limit)
        ).scalars()
        return [
            {
                "verification_id": v.id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "overall": v.overall,
                "filename": v.filename,
                "decision": _decision_dict(v.decisions[-1]) if v.decisions else None,
            }
            for v in rows
        ]


def list_verifications(limit: int = 50, offset: int = 0) -> list[dict]:
    """Newest-first summaries (no PDF bytes) with each record's latest decision."""
    if _SessionLocal is None:
        return []
    with _SessionLocal() as s:
        rows = s.execute(
            select(Verification).order_by(Verification.created_at.desc()).limit(limit).offset(offset)
        ).scalars()
        return [
            {
                **_summary_dict(v),
                "decision": _decision_dict(v.decisions[-1]) if v.decisions else None,
            }
            for v in rows
        ]


def _summary_dict(v: Verification) -> dict:
    return {
        "verification_id": v.id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "source": v.source,
        "filename": v.filename,
        "ttb_id": v.ttb_id,
        "brand_name": v.brand_name,
        "product_type": v.product_type,
        "overall": v.overall,
        "processing_ms": v.processing_ms,
        "has_pdf": v.pdf_size is not None,
    }


def _decision_dict(d: Decision) -> dict:
    return {
        "id": d.id,
        "action": d.action,
        "note": d.note,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
