import { useEffect, useState } from "react";

export interface PreviewImage {
  src: string;
  caption?: string | null;
}

export function LabelPreview({ images }: { images: PreviewImage[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  useEffect(() => {
    if (openIdx === null) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpenIdx(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openIdx]);

  if (!images.length) return null;

  return (
    <div className="preview">
      <div className="preview-label">EXTRACTED LABEL{images.length > 1 ? "S" : ""}</div>
      <div className="preview-strip">
        {images.map((img, i) => (
          <button
            key={i}
            className="preview-thumb"
            title={`Expand ${img.caption || "label image"}`}
            aria-label={`Expand ${img.caption || "label image"}`}
            onClick={() => setOpenIdx(i)}
          >
            <img src={img.src} alt={img.caption || "Extracted label"} />
          </button>
        ))}
      </div>

      {openIdx !== null && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Label image preview"
          onClick={() => setOpenIdx(null)}
        >
          <button className="lightbox-close" aria-label="Close preview" onClick={() => setOpenIdx(null)}>
            ✕
          </button>
          <img
            className="lightbox-img"
            src={images[openIdx].src}
            alt={images[openIdx].caption || "Extracted label"}
            onClick={(e) => e.stopPropagation()}
          />
          {images[openIdx].caption && <div className="lightbox-caption">{images[openIdx].caption}</div>}
        </div>
      )}
    </div>
  );
}
