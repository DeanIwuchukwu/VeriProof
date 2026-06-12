"""FastAPI app — two co-equal verification endpoints over one engine (SPEC §5).

  POST /api/verify/cola    — input mode 1: upload a COLA record (PDF)
  POST /api/verify/manual  — input mode 2: claimed fields + label image(s)

Stateless; nothing is persisted. Errors are returned as friendly JSON, never raw
stack traces (SPEC N6).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.cola.models import ClaimedFields, ColaRecord, LabelImage, ProductSource, ProductType
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
        record, result = service.verify_cola(data)
    except ValueError as e:  # provider misconfig (e.g. missing key)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 — never leak a stack trace to the client
        raise HTTPException(
            status_code=422,
            detail=f"Could not read this COLA record. Is it a valid TTB 5100.31 PDF? ({type(e).__name__})",
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
    country_of_origin: str | None = Form(None),
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
    # Country claimed manually is folded into the producer/source logic; the label-side
    # country check is regulatory and needs no claimed value.
    try:
        result = service.verify_manual(claimed, label_images)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Verification failed unexpectedly ({type(e).__name__})."
        ) from e
    return JSONResponse(_response(None, result, service.provider_name, claimed=claimed))


# ----- helpers --------------------------------------------------------------

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
