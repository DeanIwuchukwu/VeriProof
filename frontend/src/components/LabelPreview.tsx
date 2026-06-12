import { useEffect, useRef, useState } from "react";

export interface PreviewImage {
  src: string;
  caption?: string | null;
}

export function LabelPreview({ images }: { images: PreviewImage[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Esc to close, trap Tab inside the dialog, and restore focus to the trigger on close.
  useEffect(() => {
    if (openIdx === null) return;
    const prev = document.activeElement as HTMLElement | null;
    const focusables = () =>
      Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("button, [tabindex]") ?? []);
    focusables()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenIdx(null);
        return;
      }
      if (e.key !== "Tab") return;
      const f = focusables();
      if (!f.length) return;
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
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
          ref={dialogRef}
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
