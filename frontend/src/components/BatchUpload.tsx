import { useRef, useState } from "react";

export function BatchUpload({ onVerify, busy }: { onVerify: (files: File[]) => void; busy: boolean }) {
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  function add(list: FileList | null) {
    if (list) setFiles(Array.from(list));
  }

  return (
    <>
      <p className="desc">
        Drop multiple COLA PDFs — each record is verified independently and summarized in the panel
        on the right.
      </p>

      <button
        type="button"
        className="dropzone"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          add(e.dataTransfer.files);
        }}
      >
        <span className="dropzone-main">
          <strong className="dropzone-strong">Add COLA PDFs</strong> or drag them here
        </span>
        <span className="dropzone-sub">Up to 50 records per batch</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="sr-only"
        onChange={(e) => add(e.target.files)}
      />

      {files.length > 0 && (
        <div className="queue">
          {files.map((f, i) => (
            <div className="queue-row" key={`${f.name}-${i}`}>
              <span className="pdf-chip">PDF</span>
              <span className="queue-name" title={f.name}>
                {f.name}
              </span>
              <span className="queue-chip" style={{ background: "var(--nc-bg)", color: "var(--nc-text)" }}>
                {busy ? "Verifying…" : "Queued"}
              </span>
            </div>
          ))}
          <div className="queue-footer">
            {files.length} record{files.length === 1 ? "" : "s"} queued
          </div>
        </div>
      )}

      <button className="btn-primary" disabled={!files.length || busy} onClick={() => onVerify(files)}>
        {busy ? `Verifying ${files.length}…` : `Verify queue (${files.length || 0})`}
      </button>
    </>
  );
}
