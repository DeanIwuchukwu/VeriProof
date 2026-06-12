"""FastAPI app — two co-equal verification endpoints over one engine (SPEC §5).

  POST /api/verify/cola    — input mode 1: upload a COLA record (PDF)
  POST /api/verify/manual  — input mode 2: claimed fields + label image(s)

Stateless; nothing is persisted. Errors are returned as friendly JSON, never raw
stack traces (SPEC N6).
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.cola.models import ClaimedFields, ColaRecord, LabelImage, ProductSource, ProductType
from app.config import get_settings
from app.matching.verdict import VerificationResult
from app.service import VerificationService

app = FastAPI(
    title="TTB Label Verification",
    version="0.1.0",
    description="AI-assisted verification of alcohol-beverage labels against COLA application data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

_EXT_TO_FMT = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}


@lru_cache
def get_service() -> VerificationService:
    return VerificationService()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "ttb-label-verification"}


@app.post("/api/verify/cola")
async def verify_cola(
    file: UploadFile = File(..., description="A COLA record PDF (TTB Form 5100.31)."),
    service: VerificationService = Depends(get_service),
) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    try:
        record = service.parse_cola(data)
    except Exception as e:  # noqa: BLE001 — never leak a stack trace to the client
        raise HTTPException(
            status_code=422,
            detail=f"Could not read this COLA record. Is it a valid TTB 5100.31 PDF? ({type(e).__name__})",
        ) from e
    try:
        result = service.verify_record(record)
    except ValueError as e:  # provider misconfig (e.g. missing key)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 — operational failure after a successful parse
        raise HTTPException(
            status_code=503,
            detail=f"The COLA record was parsed, but verification could not be completed ({type(e).__name__}). Please try again.",
        ) from e
    return JSONResponse(_response(record, result, service.provider_name))


@app.post("/api/verify/manual")
async def verify_manual(
    images: list[UploadFile] = File(..., description="One or more label images (front/back)."),
    brand_name: str | None = Form(None),
    fanciful_name: str | None = Form(None),
    product_type: str | None = Form(None),
    source: str | None = Form(None),
    net_contents: str | None = Form(None, description="Comma- or newline-separated allowed sizes."),
    alcohol_content: str | None = Form(None),
    class_type: str | None = Form(None),
    producer: str | None = Form(None),
    service: VerificationService = Depends(get_service),
) -> JSONResponse:
    label_images = []
    for img in images:
        body = await img.read()
        if body:
            label_images.append(
                LabelImage(image_format=_fmt(img), data=body, image_type="uploaded")
            )
    if not label_images:
        raise HTTPException(status_code=422, detail="At least one non-empty label image is required.")

    claimed = ClaimedFields(
        brand_name=_clean(brand_name),
        fanciful_name=_clean(fanciful_name),
        product_type=_product_type(product_type),
        source=_source(source),
        net_contents=_split_sizes(net_contents),
        alcohol_content=_clean(alcohol_content),
        class_type_description=_clean(class_type),
        applicant_name_address=_clean(producer),
        dba_tradename=None,
    )
    # Country of origin is verified from Source (imported) + the label, not a claimed value,
    # so there is no manual country field to collect here.
    try:
        result = service.verify_manual(claimed, label_images)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"The label was uploaded, but verification could not be completed ({type(e).__name__}). Please try again.",
        ) from e
    return JSONResponse(_response(None, result, service.provider_name, claimed=claimed))


@app.post("/api/verify/batch")
async def verify_batch(
    files: list[UploadFile] = File(..., description="Multiple COLA record PDFs."),
    service: VerificationService = Depends(get_service),
) -> JSONResponse:
    """Verify many COLA records concurrently (peak-season case: 200-300 at once).

    Per-record failures are isolated — one unreadable file does not fail the batch.
    Concurrency is bounded to respect the vision provider's rate limits.
    """
    settings = get_settings()
    if len(files) > settings.batch_max_files:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files ({len(files)}). The limit is {settings.batch_max_files} per batch.",
        )
    payloads = [(f.filename or "record.pdf", await f.read()) for f in files]
    if not payloads:
        raise HTTPException(status_code=422, detail="No files were uploaded.")

    sem = asyncio.Semaphore(max(1, settings.batch_concurrency))

    async def run_one(name: str, data: bytes) -> dict:
        async with sem:
            if not data:
                return _batch_error(name, "The file is empty.")
            try:
                record = await asyncio.to_thread(service.parse_cola, data)
            except Exception as e:  # noqa: BLE001
                return _batch_error(name, f"Could not read this COLA record ({type(e).__name__}).")
            try:
                result = await asyncio.to_thread(service.verify_record, record)
                return _batch_item(name, record, result)
            except ValueError as e:  # provider misconfig (e.g. missing key)
                return _batch_error(name, str(e))
            except Exception as e:  # noqa: BLE001
                return _batch_error(
                    name,
                    f"The COLA record was parsed, but verification could not be completed ({type(e).__name__}).",
                )

    items = await asyncio.gather(*(run_one(n, d) for n, d in payloads))
    return JSONResponse({"items": items, "summary": _batch_summary(items)})


# ----- helpers --------------------------------------------------------------

def _batch_item(name: str, record: ColaRecord, result: VerificationResult) -> dict:
    counts = {"pass": 0, "flag": 0, "fail": 0}
    for f in result.fields:
        key = f.status.value.lower()
        if key in counts:
            counts[key] += 1
    return {
        "filename": name,
        "error": None,
        "ttb_id": record.claimed.ttb_id,
        "brand_name": record.claimed.brand_name,
        "product_type": record.claimed.product_type.value,
        "overall": result.overall.value,
        "processing_ms": result.processing_ms,
        "counts": counts,
        "claimed": record.claimed.model_dump(),
        "result": result.model_dump(),
        "form_version": record.form_version,
    }


def _batch_error(name: str, message: str) -> dict:
    return {
        "filename": name,
        "error": message,
        "ttb_id": None,
        "brand_name": None,
        "product_type": None,
        "overall": "ERROR",
        "processing_ms": None,
        "counts": {"pass": 0, "flag": 0, "fail": 0},
        "claimed": None,
        "result": None,
        "form_version": None,
    }


def _batch_summary(items: list[dict]) -> dict:
    summary = {"total": len(items), "PASS": 0, "FLAG": 0, "FAIL": 0, "ERROR": 0}
    for it in items:
        key = it["overall"] if it["overall"] in summary else "ERROR"
        summary[key] = summary.get(key, 0) + 1
    return summary


def _response(
    record: ColaRecord | None,
    result: VerificationResult,
    provider: str,
    claimed: ClaimedFields | None = None,
) -> dict:
    claimed_fields = record.claimed if record else claimed
    images_meta = (
        [
            {
                "image_type": im.image_type,
                "actual_dimensions": im.actual_dimensions,
                "width_px": im.width_px,
                "height_px": im.height_px,
            }
            for im in record.label_images
        ]
        if record
        else []
    )
    return {
        "claimed": claimed_fields.model_dump() if claimed_fields else None,
        "result": result.model_dump(),
        "images": images_meta,
        "form_version": record.form_version if record else None,
        "provider": provider,
    }


def _clean(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None


def _split_sizes(s: str | None) -> list[str]:
    if not s:
        return []
    parts = [p.strip() for chunk in s.split("\n") for p in chunk.split(",")]
    return [p for p in parts if p]


def _product_type(s: str | None) -> ProductType:
    table = {
        "wine": ProductType.WINE,
        "distilled spirits": ProductType.DISTILLED_SPIRITS,
        "spirits": ProductType.DISTILLED_SPIRITS,
        "malt beverage": ProductType.MALT_BEVERAGE,
        "malt": ProductType.MALT_BEVERAGE,
        "beer": ProductType.MALT_BEVERAGE,
    }
    return table.get((s or "").strip().lower(), ProductType.UNKNOWN)


def _source(s: str | None) -> ProductSource:
    table = {
        "domestic": ProductSource.DOMESTIC,
        "imported": ProductSource.IMPORTED,
        "import": ProductSource.IMPORTED,
    }
    return table.get((s or "").strip().lower(), ProductSource.UNKNOWN)


def _fmt(upload: UploadFile) -> str:
    ctype = (upload.content_type or "").lower()
    if ctype.startswith("image/"):
        sub = ctype.split("/", 1)[1]
        if sub in _EXT_TO_FMT:
            return _EXT_TO_FMT[sub]
    ext = (upload.filename or "").rsplit(".", 1)[-1].lower()
    return _EXT_TO_FMT.get(ext, "jpeg")
