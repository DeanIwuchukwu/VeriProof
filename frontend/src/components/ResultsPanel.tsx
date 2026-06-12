import { useState } from "react";
import { submitDecision } from "../api";
import type { DecisionAction, VerifyResponse } from "../types";
import { fmtDate } from "./HistoryPanel";
import {
  bannerInfo,
  DensitySwitch,
  type Density,
  ResultBody,
  toFieldView,
} from "./reportViews";

export function ResultsPanel({
  data,
  density,
  onDensity,
}: {
  data: VerifyResponse;
  density: Density;
  onDensity: (d: Density) => void;
}) {
  const fields = data.result.fields.map(toFieldView);
  const { tone, title, summary } = bannerInfo(data.result);
  const ms = data.result.processing_ms;

  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<DecisionAction | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canDecide = !!data.verification_id;

  async function decide(action: DecisionAction) {
    if (!data.verification_id) return;
    setSaving(true);
    setError(null);
    try {
      await submitDecision(data.verification_id, action, note.trim() || undefined);
      setSaved(action);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the decision.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className={`banner ${tone}`} role="status">
        <span className="banner-dot" aria-hidden="true" />
        <span className="banner-title">{title}</span>
        {summary && <span className="banner-summary">{summary}</span>}
        {ms != null && (
          <span className="time-chip" title="End-to-end processing time">
            ⏱ {(ms / 1000).toFixed(1)}s
          </span>
        )}
        <DensitySwitch density={density} onDensity={onDensity} />
      </div>

      {data.prior_verifications.length > 0 && (
        <div className="prior-banner" role="note">
          <span aria-hidden="true">↻</span>
          <span>
            Previously verified {fmtDate(data.prior_verifications[0].created_at)}
            {data.prior_verifications[0].decision ? (
              <>
                {" — "}
                <strong>
                  {data.prior_verifications[0].decision.action === "ACCEPT" ? "✓ Accepted" : "✕ Rejected"}
                </strong>
                {data.prior_verifications[0].decision.note && (
                  <> (“{data.prior_verifications[0].decision.note}”)</>
                )}
              </>
            ) : (
              " — no decision was recorded"
            )}
            {data.prior_verifications.length > 1 &&
              ` · ${data.prior_verifications.length - 1} more earlier run${data.prior_verifications.length > 2 ? "s" : ""}`}
            {" — see History"}
          </span>
        </div>
      )}

      <div className="results-body">
        <ResultBody fields={fields} density={density} />
      </div>

      <div className="result-actions">
        <span className="result-actions-hint">Agent decision:</span>
        <input
          type="text"
          className="decision-note"
          placeholder="Add a note (optional)…"
          aria-label="Agent decision note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={saved !== null}
        />
        {error && (
          <span className="decision-error" role="alert">
            {error}
          </span>
        )}
        {saved ? (
          <>
            <span className={`saved-chip ${saved === "ACCEPT" ? "accept" : "reject"}`} role="status">
              {saved === "ACCEPT" ? "✓ Accepted — saved" : "✕ Rejected — saved"}
            </span>
            <button type="button" className="chip-change" onClick={() => setSaved(null)}>
              Change
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn-reject"
              disabled={saving || !canDecide}
              title={canDecide ? undefined : "Saving is unavailable (database not configured)"}
              onClick={() => decide("REJECT")}
            >
              ✕ Reject
            </button>
            <button
              type="button"
              className="btn-accept"
              disabled={saving || !canDecide}
              title={canDecide ? undefined : "Saving is unavailable (database not configured)"}
              onClick={() => decide("ACCEPT")}
            >
              {saving ? "Saving…" : "✓ Accept"}
            </button>
          </>
        )}
      </div>
    </>
  );
}
