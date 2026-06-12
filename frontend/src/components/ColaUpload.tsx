import { useId, useRef, useState } from "react";

export function ColaUpload({
  onVerify,
  busy,
}: {
  onVerify: (file: File) => void;
  busy: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | undefined) {
    if (f) setFile(f);
  }

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        if (file) onVerify(file);
      }}
    >
      <p className="panel-help">
        Upload a COLA record (TTB Form 5100.31 PDF). The application fields and the label images are
        read from the same document — no typing needed.
      </p>

      <div
        className={`dropzone ${dragging ? "dropzone-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files[0]);
        }}
      >
        <label htmlFor={inputId} className="dropzone-label">
          <span className="dropzone-icon" aria-hidden="true">
            📄
          </span>
          <span>
            <strong>Choose a COLA PDF</strong> or drag it here
          </span>
        </label>
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>

      {file && (
        <p className="filename" aria-live="polite">
          Selected: <strong>{file.name}</strong>
        </p>
      )}

      <button type="submit" className="btn-primary" disabled={!file || busy}>
        {busy ? "Verifying…" : "Verify label"}
      </button>
    </form>
  );
}
