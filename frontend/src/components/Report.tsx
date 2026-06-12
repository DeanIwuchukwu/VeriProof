import type { Status, VerifyResponse } from "../types";
import { StatusPill } from "./StatusPill";

const OVERALL_TEXT: Record<Status, string> = {
  PASS: "All checks passed",
  FLAG: "Needs review — discrepancies found",
  FAIL: "Compliance issues found",
  INFO: "Label read — nothing to compare",
  NOT_CHECKED: "Nothing to verify",
};

export function Report({ data }: { data: VerifyResponse }) {
  const { result, claimed, images, form_version } = data;

  return (
    <section className="report" aria-label="Verification report">
      <div className={`overall overall-${result.overall.toLowerCase()}`} role="status">
        <div className="overall-main">
          <StatusPill status={result.overall} />
          <span className="overall-text">{OVERALL_TEXT[result.overall]}</span>
        </div>
        <div className="overall-meta">
          {result.processing_ms != null && (
            <span
              className={`time-badge ${result.processing_ms <= 5000 ? "time-ok" : "time-slow"}`}
              title="End-to-end processing time"
            >
              ⏱ {(result.processing_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>
      </div>

      {result.notes && (
        <p className="notice" role="alert">
          {result.notes}
        </p>
      )}

      <table className="fields">
        <caption className="sr-only">Field-by-field verification results</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Application says</th>
            <th scope="col">Label shows</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {result.fields.map((f) => (
            <tr key={f.field}>
              <th scope="row" className="field-name">
                {f.label}
              </th>
              <td className="cell-claimed">{f.claimed ?? <span className="muted">—</span>}</td>
              <td className="cell-extracted">{f.extracted ?? <span className="muted">—</span>}</td>
              <td className="cell-result">
                <StatusPill status={f.status} />
                <p className="reason">{f.reason}</p>
                {f.extracted && f.confidence > 0 && (
                  <p className="confidence">Read confidence: {Math.round(f.confidence * 100)}%</p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl className="meta-grid">
        {claimed?.ttb_id && (
          <div>
            <dt>TTB ID</dt>
            <dd>{claimed.ttb_id}</dd>
          </div>
        )}
        {images.length > 0 && (
          <div>
            <dt>Label images</dt>
            <dd>{images.map((i) => i.image_type || "label").join(", ")}</dd>
          </div>
        )}
        {form_version && (
          <div>
            <dt>Form</dt>
            <dd>{form_version}</dd>
          </div>
        )}
      </dl>

      <p className="disclaimer">
        This tool assists review by flagging items for a human compliance agent. It does not approve
        or reject applications. Type size, characters-per-inch, and contrasting-background checks are
        outside COLA certification scope (per TTB qualification) and are not evaluated here.
      </p>
    </section>
  );
}
