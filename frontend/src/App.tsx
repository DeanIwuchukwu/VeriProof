import { useState } from "react";
import { verifyBatch, verifyCola, verifyManual } from "./api";
import { BatchResults } from "./components/BatchResults";
import { BatchUpload } from "./components/BatchUpload";
import { ColaUpload } from "./components/ColaUpload";
import { ManualForm } from "./components/ManualForm";
import { Report } from "./components/Report";
import type { BatchResponse, ManualFields, VerifyResponse } from "./types";

type Mode = "cola" | "manual" | "batch";

const TABS: { id: Mode; label: string }[] = [
  { id: "cola", label: "Upload COLA record" },
  { id: "manual", label: "Enter values manually" },
  { id: "batch", label: "Batch (many records)" },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("cola");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [batch, setBatch] = useState<BatchResponse | null>(null);

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
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead-inner">
          <p className="agency">Alcohol and Tobacco Tax and Trade Bureau</p>
          <h1>Label Verification</h1>
          <p className="tagline">
            Check that an alcohol-beverage label matches its COLA application — in seconds.
          </p>
        </div>
      </header>

      <main className="container">
        <div className="tabs" role="tablist" aria-label="Verification mode">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={mode === t.id}
              className={`tab ${mode === t.id ? "tab-active" : ""}`}
              onClick={() => switchMode(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {mode === "cola" && <ColaUpload busy={busy} onVerify={(file) => run(() => verifyCola(file))} />}
        {mode === "manual" && (
          <ManualForm
            busy={busy}
            onVerify={(fields: ManualFields, images: File[]) => run(() => verifyManual(fields, images))}
          />
        )}
        {mode === "batch" && <BatchUpload busy={busy} onVerify={runBatch} />}

        <div aria-live="polite">
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {batch && <BatchResults data={batch} />}
          {result && <Report data={result} />}
        </div>
      </main>

      <footer className="footer">
        Prototype — assistive tool for compliance review. No data is stored.
      </footer>
    </div>
  );
}
