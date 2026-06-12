"""Upscale small label images so vision models can resolve fine print.

gpt-5.4-mini missed the small back-label "Imported by ..." line on a 241px-wide
image even at detail="high"; enlarging the image before the call makes that print
legible to the model. Uses PyMuPDF (already a dependency) — no Pillow needed.
"""

from __future__ import annotations

import fitz

# Long edge (px) to enlarge small images to. 1024 reliably makes back-label small
# print (e.g. the importer line) legible to the model while keeping other small
# text stable; a more aggressive 1536 was observed to increase net-contents
# misreads on tiny labels. Larger images are left untouched.
DEFAULT_TARGET_LONG_EDGE = 1024


def upscale_image(
    data: bytes,
    image_format: str | None,
    target_long_edge: int = DEFAULT_TARGET_LONG_EDGE,
) -> tuple[bytes, str]:
    """Return (bytes, format) enlarged so the long edge ≈ ``target_long_edge``.

    Images already at/over the target are returned unchanged. Decode/encode
    failures fall back to the original bytes — preprocessing must never break
    extraction.
    """
    fmt = image_format or "png"
    try:
        doc = fitz.open(stream=data, filetype=fmt)
        try:
            page = doc[0]
            long_edge = max(page.rect.width, page.rect.height)
            if long_edge <= 0 or long_edge >= target_long_edge:
                return data, fmt
            zoom = target_long_edge / long_edge
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes(output="jpg", jpg_quality=90), "jpeg"
        finally:
            doc.close()
    except Exception:  # noqa: BLE001 — never let preprocessing break extraction
        return data, fmt
