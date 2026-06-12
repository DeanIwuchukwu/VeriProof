import { useMemo, useState } from "react";
import { submitDecision } from "../api";
import type { BatchItem, BatchResponse, DecisionAction, DisplayStatus } from "../types";
import { ResultBody, StatusBadge, toFieldView } from "./reportViews";

type Filter = "ALL" | DisplayStatus;

export function BatchResultsPanel({ data }: { data: BatchResponse }) {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [open, setOpen] = useState<string | null>(null);
  // Decisions saved this session, keyed by verification_id (server keeps the record).
  const [decided, setDecided] = useState<Record<string, DecisionAction>>({});
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const s = data.summary;

  async function decide(it: BatchItem, action: DecisionAction) {
    const id = it.verification_id;
    if (!id || busyIds.has(id)) return;
    setError(null);
    setBusyIds((b) => new Set(b).add(id));
    try {
      await submitDecision(id, action);
      setDecided((d) => ({ ...d, [id]: action }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the decision.");
    } finally {
      setBusyIds((b) => {
        const next = new Set(b);
        next.delete(id);
        return next;
      });
    }
  }

  async function acceptAllPassing(items: BatchItem[]) {
    const targets = items.filter(
      (it) => it.overall === "PASS" && it.verification_id && !decided[it.verification_id],
    );
    await Promise.all(targets.map((it) => decide(it, "ACCEPT")));
  }

  const tone = s.FAIL || s.ERROR ? "fail" : s.FLAG ? "flag" : "";
  const title =
    s.FAIL || s.ERROR ? "Issues found" : s.FLAG ? "Some records need review" : "All records passed";
  const summary = [
    `${s.total} record${s.total === 1 ? "" : "s"}`,
    s.PASS && `${s.PASS} passed`,
    s.FLAG && `${s.FLAG} review`,
    s.FAIL && `${s.FAIL} failed`,
    s.ERROR && `${s.ERROR} error`,
  ]
    .filter(Boolean)
    .join(" · ");

  const rows = useMemo(
    () => data.items.filter((it) => filter === "ALL" || it.overall === filter),
    [data.items, filter],
  );
  const anyPass = useMemo(() => rows.some((it) => it.overall === "PASS"), [rows]);

  const chips: { id: Filter; label: string; n: number }[] = [
    { id: "ALL", label: "All", n: s.total },
    { id: "PASS", label: "Passed", n: s.PASS },
    { id: "FLAG", label: "Review", n: s.FLAG },
    { id: "FAIL", label: "Failed", n: s.FAIL },
    { id: "ERROR", label: "Errors", n: s.ERROR },
  ];

  return (
    <>
      <div className={`banner ${tone}`} role="status">
        <span className="banner-dot" aria-hidden="true" />
        <span className="banner-title">{title}</span>
        <span className="banner-summary">{summary}</span>
      </div>

      <div className="banner" style={{ background: "#fff", borderBottomColor: "var(--divider-2)" }}>
        <div className="batch-filter">
          {chips
            .filter((c) => c.id === "ALL" || c.n > 0)
            .map((c) => (
              <button
                key={c.id}
                className={`filter-chip ${filter === c.id ? "active" : ""}`}
                aria-pressed={filter === c.id}
                onClick={() => setFilter(c.id)}
              >
                {c.label} {c.n}
              </button>
            ))}
        </div>
        <button className="csv-btn" onClick={() => downloadCsv(data.items)}>
          ⭳ Export CSV
        </button>
      </div>

      <div className="results-body">
        <div className="batch-table-head">
          <span className="col-label">FILE</span>
          <span className="col-label">BRAND</span>
          <span className="col-label">TYPE</span>
          <span className="col-label">RESULT</span>
          <span className="col-label" style={{ textAlign: "right" }}>
            TIME
          </span>
          <span className="col-label" style={{ textAlign: "right" }}>
            DECISION
          </span>
        </div>
        {rows.map((it) => (
          <BatchRow
            key={it.filename}
            it={it}
            open={open === it.filename}
            onToggle={() => setOpen(open === it.filename ? null : it.filename)}
            decision={it.verification_id ? (decided[it.verification_id] ?? null) : null}
            busy={!!it.verification_id && busyIds.has(it.verification_id)}
            onDecide={(action) => decide(it, action)}
          />
        ))}
        {(anyPass || error) && (
          <div className="batch-foot">
            {error && (
              <span className="decision-error" role="alert">
                {error}
              </span>
            )}
            {anyPass && (
              <button type="button" className="btn-accept" onClick={() => acceptAllPassing(rows)}>
                ✓ Accept All (Pass)
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

function BatchRow({
  it,
  open,
  onToggle,
  decision,
  busy,
  onDecide,
}: {
  it: BatchItem;
  open: boolean;
  onToggle: () => void;
  decision: DecisionAction | null;
  busy: boolean;
  onDecide: (action: DecisionAction) => void;
}) {
  const drillable = !!it.result;
  const canDecide = !!it.verification_id;
  return (
    <>
      <div
        className={`batch-row ${open ? "open" : ""}`}
        onClick={drillable ? onToggle : undefined}
        role={drillable ? "button" : undefined}
        aria-expanded={drillable ? open : undefined}
      >
        <span className="cell-field" title={it.filename}>
          {drillable && <span className="compare-arrow">{open ? "▾ " : "▸ "}</span>}
          {it.filename}
        </span>
        <span className="cell-val">{it.brand_name ?? "—"}</span>
        <span className="cell-val">{it.product_type ?? "—"}</span>
        <span>
          {it.error ? <StatusBadge status="FAIL" /> : <BatchBadge overall={it.overall} />}
        </span>
        <span className="cell-val" style={{ textAlign: "right" }}>
          {it.processing_ms != null ? `${(it.processing_ms / 1000).toFixed(1)}s` : "—"}
        </span>
        <span className="batch-actions" onClick={(e) => e.stopPropagation()}>
          {!it.error &&
            (decision ? (
              <span className={`saved-chip ${decision === "ACCEPT" ? "accept" : "reject"}`} role="status">
                {decision === "ACCEPT" ? "✓ Accepted" : "✕ Rejected"}
              </span>
            ) : (
              <>
                <button
                  type="button"
                  className="btn-reject btn-mini"
                  disabled={busy || !canDecide}
                  title={canDecide ? undefined : "Saving is unavailable (database not configured)"}
                  onClick={() => onDecide("REJECT")}
                >
                  Reject
                </button>
                <button
                  type="button"
                  className="btn-accept btn-mini"
                  disabled={busy || !canDecide}
                  title={canDecide ? undefined : "Saving is unavailable (database not configured)"}
                  onClick={() => onDecide("ACCEPT")}
                >
                  {busy ? "…" : "Accept"}
                </button>
              </>
            ))}
        </span>
      </div>
      {open && it.result && (
        <div className="batch-drill">
          <ResultBody fields={it.result.fields.map(toFieldView)} density="table" />
        </div>
      )}
      {open && it.error && (
        <div className="batch-drill">
          <p className="note" style={{ padding: "10px 0" }}>
            {it.error}
          </p>
        </div>
      )}
    </>
  );
}

function BatchBadge({ overall }: { overall: DisplayStatus }) {
  if (overall === "ERROR") return <span className="badge badge-fail">ERROR</span>;
  return <StatusBadge status={overall} />;
}

function downloadCsv(items: BatchItem[]) {
  const head = ["filename", "ttb_id", "brand_name", "product_type", "overall", "pass", "flag", "fail", "processing_ms", "error"];
  const esc = (v: unknown) => {
    const str = String(v ?? "");
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
  };
  const lines = [head.join(",")];
  for (const it of items) {
    lines.push(
      [it.filename, it.ttb_id, it.brand_name, it.product_type, it.overall, it.counts.pass, it.counts.flag, it.counts.fail, it.processing_ms, it.error]
        .map(esc)
        .join(","),
    );
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ttb-batch-results.csv";
  a.click();
  URL.revokeObjectURL(url);
}
