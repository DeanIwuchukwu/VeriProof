import type { FieldVerdict, Status, VerificationResult } from "../types";

export type Density = "table" | "cards" | "triage";

// A field shaped for the views (mirrors the design's per-field data model).
export interface FieldView {
  field: string;
  name: string;
  app: string;
  label: string;
  note: string;
  confText: string;
  status: Status;
  flag: boolean; // needs attention: not a clean PASS, or read with low confidence
}

const LOW_CONFIDENCE = 0.9;

export function toFieldView(f: FieldVerdict): FieldView {
  const conf = f.confidence ?? 0;
  const showConf = !!f.extracted && conf > 0;
  return {
    field: f.field,
    name: f.label,
    app: f.claimed ?? "—",
    label: f.extracted ?? "—",
    note: f.reason,
    confText: showConf ? `Read confidence ${Math.round(conf * 100)}%` : "",
    status: f.status,
    flag: f.status !== "PASS" || (showConf && conf < LOW_CONFIDENCE),
  };
}

const BADGE_LABEL: Record<Status, string> = {
  PASS: "PASS",
  FLAG: "FLAG",
  FAIL: "FAIL",
  INFO: "INFO",
  NOT_CHECKED: "NOT CHECKED",
};

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{BADGE_LABEL[status]}</span>;
}

/** Banner copy + tone + summary counts derived from a result. */
export function bannerInfo(result: VerificationResult) {
  const c = { pass: 0, advisory: 0, notChecked: 0, fail: 0 };
  for (const f of result.fields) {
    if (f.status === "PASS") c.pass++;
    else if (f.status === "INFO" || f.status === "FLAG") c.advisory++;
    else if (f.status === "NOT_CHECKED") c.notChecked++;
    else if (f.status === "FAIL") c.fail++;
  }
  const tone = result.overall === "FAIL" ? "fail" : result.overall === "FLAG" ? "flag" : "";
  const title =
    result.overall === "FAIL"
      ? "Compliance issues found"
      : result.overall === "FLAG"
        ? "Needs review"
        : "All checks passed";
  const parts: string[] = [];
  if (c.pass) parts.push(`${c.pass} passed`);
  if (c.advisory) parts.push(`${c.advisory} advisory`);
  if (c.fail) parts.push(`${c.fail} failed`);
  if (c.notChecked) parts.push(`${c.notChecked} not checked`);
  return { tone, title, summary: parts.join(" · ") };
}

export function DensitySwitch({
  density,
  onDensity,
}: {
  density: Density;
  onDensity: (d: Density) => void;
}) {
  const opts: Density[] = ["table", "cards", "triage"];
  return (
    <span className="density-switch" role="tablist" aria-label="Result density">
      {opts.map((d) => (
        <button
          key={d}
          role="tab"
          aria-selected={density === d}
          className={`density-btn ${density === d ? "active" : ""}`}
          onClick={() => onDensity(d)}
        >
          {d[0].toUpperCase() + d.slice(1)}
        </button>
      ))}
    </span>
  );
}

export function ResultBody({ fields, density }: { fields: FieldView[]; density: Density }) {
  if (density === "cards") return <ReportCards fields={fields} />;
  if (density === "triage") return <ReportTriage fields={fields} />;
  return <ReportTable fields={fields} />;
}

function ReportTable({ fields }: { fields: FieldView[] }) {
  return (
    <>
      <div className="table-head">
        <span className="col-label">FIELD</span>
        <span className="col-label">APPLICATION SAYS</span>
        <span className="col-label">LABEL SHOWS</span>
        <span className="col-label">RESULT</span>
      </div>
      {fields.map((f) => (
        <div className="table-row" key={f.field}>
          <span className="cell-field">{f.name}</span>
          <span className="cell-val">{f.app}</span>
          <span className="cell-val clamp-2" title={f.label}>
            {f.label}
          </span>
          <span className="result-cell">
            <StatusBadge status={f.status} />
            <span className="result-text">
              <span className="note clamp-2" title={f.note}>
                {f.note}
              </span>
              {f.confText && <span className="conf">{f.confText}</span>}
            </span>
          </span>
        </div>
      ))}
    </>
  );
}

function ReportCards({ fields }: { fields: FieldView[] }) {
  return (
    <div className="cards-grid">
      {fields.map((f) => (
        <div className="card" key={f.field}>
          <div className="card-head">
            <span className="card-name">{f.name}</span>
            <StatusBadge status={f.status} />
          </div>
          <div className="card-compare">
            <span className="mini">
              <span className="mini-label">APPLICATION</span>
              <span className="mini-val" title={f.app}>
                {f.app}
              </span>
            </span>
            <span className="mini">
              <span className="mini-label">LABEL</span>
              <span className="mini-val" title={f.label}>
                {f.label}
              </span>
            </span>
          </div>
          <span className="card-note" title={f.note}>
            {f.note}
          </span>
        </div>
      ))}
    </div>
  );
}

function ReportTriage({ fields }: { fields: FieldView[] }) {
  const attention = fields.filter((f) => f.flag);
  const passed = fields.filter((f) => !f.flag);
  return (
    <div className="triage">
      {attention.length > 0 && (
        <div className="triage-section">
          <span className="triage-title attention">NEEDS ATTENTION ({attention.length})</span>
          {attention.map((f) => (
            <div key={f.field} className={`attn-card ${f.status === "FAIL" ? "is-fail" : ""}`}>
              <div className="attn-head">
                <StatusBadge status={f.status} />
                <span className="attn-name">{f.name}</span>
                {f.confText && <span className="attn-conf">{f.confText}</span>}
              </div>
              <span className="attn-note">{f.note}</span>
              <span className="attn-compare">
                <span className="compare-tag">APP</span>
                <span>{f.app}</span>
                <span className="compare-arrow">→</span>
                <span className="compare-tag">LABEL</span>
                <span className="compare-label" title={f.label}>
                  {f.label}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
      {passed.length > 0 && (
        <div className="triage-section">
          <span className="triage-title passed">PASSED ({passed.length})</span>
          <div className="passed-list">
            {passed.map((f) => (
              <div key={f.field} className="passed-row">
                <span className="check" aria-hidden="true">
                  ✓
                </span>
                <span className="passed-name">{f.name}</span>
                <span className="passed-val">{f.app}</span>
                <span className="compare-arrow" aria-hidden="true">
                  →
                </span>
                <span className="passed-val" title={f.label}>
                  {f.label}
                </span>
                {f.confText && <span className="passed-conf">{f.confText}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
