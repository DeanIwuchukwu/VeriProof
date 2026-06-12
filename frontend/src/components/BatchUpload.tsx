import { useId, useState } from "react";

export function BatchUpload({
  onVerify,
  busy,
}: {
  onVerify: (files: File[]) => void;
  busy: boolean;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const inputId = useId();

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        if (files.length) onVerify(files);
      }}
    >
      <p className="panel-help">
        Upload many COLA records at once (the peak-season case). Each is verified independently and
        the results appear in a sortable table you can export.
      </p>

      <div className="field-group">
        <label htmlFor={inputId}>COLA record PDFs</label>
        <input
          id={inputId}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
        {files.length > 0 && (
          <p className="filename" aria-live="polite">
            {files.length} record{files.length > 1 ? "s" : ""} selected
          </p>
        )}
      </div>

      <button type="submit" className="btn-primary" disabled={!files.length || busy}>
        {busy ? `Verifying ${files.length} record${files.length > 1 ? "s" : ""}…` : "Verify all"}
      </button>
      {busy && (
        <p className="panel-help" role="status">
          Large batches can take a while — each record is read by the AI in turn.
        </p>
      )}
    </form>
  );
}
