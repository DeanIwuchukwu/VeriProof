import { useEffect, useMemo, useState } from "react";
import { verifyBatch, verifyCola, verifyManual } from "./api";
import { BatchResultsPanel } from "./components/BatchResultsPanel";
import { BatchUpload } from "./components/BatchUpload";
import { ColaUpload } from "./components/ColaUpload";
import { LabelPreview, type PreviewImage } from "./components/LabelPreview";
import { ManualForm } from "./components/ManualForm";
import { ResultsPanel } from "./components/ResultsPanel";
import type { Density } from "./components/reportViews";
import type { BatchResponse, ManualFields, VerifyResponse } from "./types";

type Mode = "upload" | "manual" | "batch";

const TABS: { id: Mode; label: string }[] = [
  { id: "upload", label: "Upload COLA" },
  { id: "manual", label: "Manual entry" },
  { id: "batch", label: "Batch" },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("upload");
  const [density, setDensity] = useState<Density>("table");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [batch, setBatch] = useState<BatchResponse | null>(null);
  const [manualFiles, setManualFiles] = useState<File[]>([]);
  const [manualUrls, setManualUrls] = useState<string[]>([]);

  // Object URLs for previewing manually-attached images (no backend bytes for manual mode).
  useEffect(() => {
    if (!manualFiles.length) {
      setManualUrls([]);
      return;
    }
    const urls = manualFiles.map((f) => URL.createObjectURL(f));
    setManualUrls(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [manualFiles]);

  const previewImages: PreviewImage[] = useMemo(() => {
    if (!result || mode === "batch") return [];
    if (mode === "upload") {
      return result.images
        .filter((i) => i.data_uri)
        .map((i) => ({ src: i.data_uri as string, caption: i.image_type }));
    }
    return manualUrls.map((u, i) => ({ src: u, caption: manualFiles[i]?.name ?? null }));
  }, [result, mode, manualUrls, manualFiles]);

  function reset() {
    setError(null);
    setResult(null);
    setBatch(null);
  }

  async function run(fn: () => Promise<VerifyResponse>) {
    setBusy(true);
    reset();
    try {
      setResult(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function runBatch(files: File[]) {
    setBusy(true);
    reset();
    try {
      setBatch(await verifyBatch(files));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    reset();
    setManualFiles([]);
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-mono">TTB</div>
        <div>
          <div className="header-eyebrow">ALCOHOL AND TOBACCO TAX AND TRADE BUREAU</div>
          <h1 className="header-title">Label Verification</h1>
        </div>
        <div className="header-tagline">Check that a label matches its COLA application — in seconds.</div>
      </header>

      <main className="main">
        {/* Input panel */}
        <section className="panel" aria-label="Verification input">
          <div className="tabs" role="tablist" aria-label="Input mode">
            {TABS.map((t) => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                aria-selected={mode === t.id}
                aria-controls="input-panel"
                className={`tab ${mode === t.id ? "active" : ""}`}
                onClick={() => switchMode(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="panel-body" id="input-panel" role="tabpanel" aria-labelledby={`tab-${mode}`}>
            {mode === "upload" && <ColaUpload busy={busy} onVerify={(file) => run(() => verifyCola(file))} />}
            {mode === "manual" && (
              <ManualForm
                busy={busy}
                onVerify={(fields: ManualFields, images: File[]) => {
                  setManualFiles(images);
                  run(() => verifyManual(fields, images));
                }}
              />
            )}
            {mode === "batch" && <BatchUpload busy={busy} onVerify={runBatch} />}

            {mode !== "batch" && previewImages.length > 0 && <LabelPreview images={previewImages} />}

            <p className="panel-note">
              This tool assists review by flagging items for a human compliance agent — it does not
              approve or reject applications.
            </p>
          </div>
        </section>

        {/* Results panel */}
        <section className="panel" aria-label="Verification results">
          {busy ? (
            <div className="panel-state">
              <div className="spinner" aria-hidden="true" />
              <span className="panel-state-title">
                {mode === "batch" ? "Verifying records…" : "Reading document…"}
              </span>
              <span className="panel-state-sub">
                Extracting application fields and label images, then checking each field.
              </span>
            </div>
          ) : error ? (
            <div className="panel-state error" role="alert">
              <span className="panel-state-title">Couldn’t complete verification</span>
              <span className="panel-state-sub">{error}</span>
            </div>
          ) : batch ? (
            <BatchResultsPanel data={batch} />
          ) : result ? (
            <ResultsPanel data={result} density={density} onDensity={setDensity} />
          ) : (
            <div className="panel-state">
              <span className="panel-state-title">No record verified yet</span>
              <span className="panel-state-sub">
                Upload a COLA record, enter values manually, or run a batch to see the field-by-field
                report here.
              </span>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
