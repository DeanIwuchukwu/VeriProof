import { useState } from "react";
import { verifyCola, verifyManual } from "./api";
import { ColaUpload } from "./components/ColaUpload";
import { ManualForm } from "./components/ManualForm";
import { Report } from "./components/Report";
import type { ManualFields, VerifyResponse } from "./types";

type Mode = "cola" | "manual";

export default function App() {
  const [mode, setMode] = useState<Mode>("cola");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  async function run(fn: () => Promise<VerifyResponse>) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setResult(null);
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
          <button
            role="tab"
            aria-selected={mode === "cola"}
            className={`tab ${mode === "cola" ? "tab-active" : ""}`}
            onClick={() => switchMode("cola")}
          >
            Upload COLA record
          </button>
          <button
            role="tab"
            aria-selected={mode === "manual"}
            className={`tab ${mode === "manual" ? "tab-active" : ""}`}
            onClick={() => switchMode("manual")}
          >
            Enter values manually
          </button>
        </div>

        {mode === "cola" ? (
          <ColaUpload busy={busy} onVerify={(file) => run(() => verifyCola(file))} />
        ) : (
          <ManualForm
            busy={busy}
            onVerify={(fields: ManualFields, images: File[]) =>
              run(() => verifyManual(fields, images))
            }
          />
        )}

        <div aria-live="polite">
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {result && <Report data={result} />}
        </div>
      </main>

      <footer className="footer">
        Prototype — assistive tool for compliance review. No data is stored.
      </footer>
    </div>
  );
}
