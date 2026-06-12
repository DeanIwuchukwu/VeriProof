import { useEffect, useRef, useState } from "react";

const FileIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
);

function formatSize(bytes: number): string {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function ColaUpload({ onVerify, busy }: { onVerify: (file: File) => void; busy: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Object URL so the uploaded PDF can be previewed in the lightbox (browser-native viewer).
  useEffect(() => {
    if (!file) {
      setFileUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFileUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  return (
    <>
      <p className="desc">
        Upload a COLA record (TTB Form 5100.31 PDF). Application fields and label images are read from
        the same document — no typing needed.
      </p>

      <button
        type="button"
        className="dropzone"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
        }}
      >
        <FileIcon />
        <span className="dropzone-main">
          <strong className="dropzone-strong">Choose a COLA PDF</strong> or drag it here
        </span>
        <span className="dropzone-sub">PDF up to 25 MB</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      {file && (
        <div className="file-row">
          <span className="pdf-chip">PDF</span>
          <button
            type="button"
            className="file-meta file-meta-btn"
            title="Click to preview the PDF"
            onClick={() => setExpanded(true)}
          >
            <span className="file-name">{file.name}</span>
            <span className="file-size">{formatSize(file.size)} · click to preview</span>
          </button>
          <button
            className="file-remove"
            title="Remove file"
            onClick={() => {
              setFile(null);
              setExpanded(false);
            }}
          >
            ✕
          </button>
        </div>
      )}

      <button className="btn-primary" disabled={!file || busy} onClick={() => file && onVerify(file)}>
        {busy ? "Reading document…" : "Verify label"}
      </button>

      {expanded && fileUrl && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="COLA PDF preview"
          onClick={() => setExpanded(false)}
        >
          <button className="lightbox-close" aria-label="Close preview" onClick={() => setExpanded(false)}>
            ✕
          </button>
          <iframe
            className="lightbox-pdf"
            src={fileUrl}
            title={file?.name ?? "COLA PDF"}
            onClick={(e) => e.stopPropagation()}
          />
          {file && <div className="lightbox-caption">{file.name}</div>}
        </div>
      )}
    </>
  );
}
