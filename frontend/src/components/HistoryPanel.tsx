import { useEffect, useMemo, useState } from "react";
import { deleteVerification, getVerificationDetail, listVerifications, pdfUrl } from "../api";
import type { HistoryDetail, HistoryItem } from "../types";
import { ResultBody, StatusBadge, toFieldView } from "./reportViews";

const TrashIcon = () => (
  <svg
    width="13"
    height="13"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M3 6h18" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
);

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type HistoryFilter = "ALL" | "PASS" | "FLAG" | "FAIL";

export function HistoryPanel() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [filter, setFilter] = useState<HistoryFilter>("ALL");
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, HistoryDetail>>({});
  const [detailError, setDetailError] = useState<string | null>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  // Repeat runs of the same record (same TTB ID) are grouped: newest shown,
  // a "×N runs" chip expands the older ones. Records without a TTB ID stand alone.
  // Filtering happens per run, before grouping.
  const groups = useMemo(() => {
    if (!items) return [];
    const visible = filter === "ALL" ? items : items.filter((it) => it.overall === filter);
    const map = new Map<string, HistoryItem[]>();
    for (const it of visible) {
      const key = it.ttb_id ?? it.verification_id;
      const arr = map.get(key);
      if (arr) arr.push(it);
      else map.set(key, [it]);
    }
    return [...map.entries()];
  }, [items, filter]);

  const chips = useMemo(() => {
    const n = (s: HistoryFilter) =>
      items ? items.filter((it) => it.overall === s).length : 0;
    return [
      { id: "ALL" as HistoryFilter, label: "All", n: items?.length ?? 0 },
      { id: "PASS" as HistoryFilter, label: "Passed", n: n("PASS") },
      { id: "FLAG" as HistoryFilter, label: "Review", n: n("FLAG") },
      { id: "FAIL" as HistoryFilter, label: "Failed", n: n("FAIL") },
    ];
  }, [items]);

  function toggleGroup(key: string) {
    setOpenGroups((g) => {
      const next = new Set(g);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function load() {
    setItems(null);
    setError(null);
    setOpenId(null);
    try {
      setItems((await listVerifications()).items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load history.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function remove(it: HistoryItem) {
    const what = it.filename ?? it.brand_name ?? "this record";
    if (!window.confirm(`Delete the saved verification of ${what} (and its decisions)? This cannot be undone.`)) {
      return;
    }
    try {
      await deleteVerification(it.verification_id);
      setItems((list) => (list ? list.filter((x) => x.verification_id !== it.verification_id) : list));
      if (openId === it.verification_id) setOpenId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the record.");
    }
  }

  async function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setDetailError(null);
    if (!details[id]) {
      try {
        const d = await getVerificationDetail(id);
        setDetails((m) => ({ ...m, [id]: d }));
      } catch (e) {
        setDetailError(e instanceof Error ? e.message : "Could not load this record.");
      }
    }
  }

  if (error) {
    return (
      <div className="panel-state error" role="alert">
        <span className="panel-state-title">Couldn’t load history</span>
        <span className="panel-state-sub">{error}</span>
      </div>
    );
  }
  if (items === null) {
    return (
      <div className="panel-state">
        <div className="spinner" aria-hidden="true" />
        <span className="panel-state-title">Loading saved verifications…</span>
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="panel-state">
        <span className="panel-state-title">No saved verifications yet</span>
        <span className="panel-state-sub">
          Verify a record and it will appear here, along with any reviewer decision.
        </span>
      </div>
    );
  }

  return (
    <>
      <div className="banner" role="status">
        <span className="banner-dot" aria-hidden="true" />
        <span className="banner-title">Saved verifications</span>
        <span className="banner-summary">
          {groups.length} record{groups.length === 1 ? "" : "s"}
          {items.length !== groups.length &&
            ` · ${items.length} run${items.length === 1 ? "" : "s"}`}
          {" · newest first"}
        </span>
        <button className="csv-btn" style={{ marginLeft: "auto" }} onClick={() => void load()}>
          ↻ Refresh
        </button>
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
      </div>

      <div className="results-body">
        <div className="history-head">
          <span className="col-label">DATE</span>
          <span className="col-label">FILE / SOURCE</span>
          <span className="col-label">BRAND</span>
          <span className="col-label">RESULT</span>
          <span className="col-label">DECISION</span>
          <span className="col-label" aria-hidden="true" />
        </div>
        {groups.length === 0 && (
          <p className="note" style={{ padding: "14px 16px" }}>
            No saved runs match this filter.
          </p>
        )}
        {groups.map(([key, group]) => {
          const groupOpen = openGroups.has(key);
          const visible = groupOpen ? group : [group[0]];
          return visible.map((it, idx) => {
            const open = openId === it.verification_id;
            const detail = details[it.verification_id];
            return (
              <HistoryRow
                key={it.verification_id}
                it={it}
                older={idx > 0}
                runCount={idx === 0 ? group.length : undefined}
                runsOpen={groupOpen}
                onToggleRuns={() => toggleGroup(key)}
                open={open}
                detail={open ? detail : undefined}
                detailError={open ? detailError : null}
                onToggle={() => void toggle(it.verification_id)}
                onDelete={() => void remove(it)}
              />
            );
          });
        })}
      </div>
    </>
  );
}

function HistoryRow({
  it,
  open,
  detail,
  detailError,
  onToggle,
  onDelete,
  older = false,
  runCount,
  runsOpen = false,
  onToggleRuns,
}: {
  it: HistoryItem;
  open: boolean;
  detail?: HistoryDetail;
  detailError: string | null;
  onToggle: () => void;
  onDelete: () => void;
  older?: boolean;
  runCount?: number;
  runsOpen?: boolean;
  onToggleRuns?: () => void;
}) {
  return (
    <>
      <div
        className={`history-row ${open ? "open" : ""} ${older ? "older" : ""}`}
        onClick={onToggle}
        role="button"
        aria-expanded={open}
      >
        <span className="cell-val">{fmtDate(it.created_at)}</span>
        <span className="cell-field" title={it.filename ?? undefined}>
          <span className="compare-arrow">{open ? "▾ " : "▸ "}</span>
          {it.filename ?? (it.source === "manual" ? "Manual entry" : it.source)}
          {runCount != null && runCount > 1 && (
            <button
              type="button"
              className="runs-chip"
              title={runsOpen ? "Hide earlier runs" : `Show ${runCount - 1} earlier run${runCount > 2 ? "s" : ""}`}
              aria-expanded={runsOpen}
              onClick={(e) => {
                e.stopPropagation();
                onToggleRuns?.();
              }}
            >
              ×{runCount} runs {runsOpen ? "▴" : "▾"}
            </button>
          )}
        </span>
        <span className="cell-val">{it.brand_name ?? "—"}</span>
        <span>
          <StatusBadge status={it.overall} />
        </span>
        <span>
          {it.decision ? (
            <span className={`saved-chip ${it.decision.action === "ACCEPT" ? "accept" : "reject"}`}>
              {it.decision.action === "ACCEPT" ? "✓ Accepted" : "✕ Rejected"}
            </span>
          ) : (
            <span className="cell-val">—</span>
          )}
        </span>
        <span onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="row-delete"
            title="Delete this saved verification"
            aria-label={`Delete saved verification of ${it.filename ?? it.brand_name ?? "record"}`}
            onClick={onDelete}
          >
            <TrashIcon />
          </button>
        </span>
      </div>

      {open && (
        <div className="batch-drill">
          {detailError ? (
            <p className="note" style={{ padding: "10px 0" }}>
              {detailError}
            </p>
          ) : !detail ? (
            <p className="note" style={{ padding: "10px 0" }}>
              Loading record…
            </p>
          ) : (
            <>
              <div className="history-meta">
                {detail.decisions.length === 0 ? (
                  <span className="note">No reviewer decision recorded.</span>
                ) : (
                  detail.decisions.map((d) => (
                    <span key={d.id} className="history-decision">
                      <span className={`saved-chip ${d.action === "ACCEPT" ? "accept" : "reject"}`}>
                        {d.action === "ACCEPT" ? "✓ Accepted" : "✕ Rejected"}
                      </span>
                      {d.note && (
                        <span className="history-note" title={d.note}>
                          “{d.note}”
                        </span>
                      )}
                      <span className="history-ts">{fmtDate(d.created_at)}</span>
                    </span>
                  ))
                )}
                {detail.has_pdf && (
                  <a
                    className="csv-btn"
                    style={{ marginLeft: "auto" }}
                    href={pdfUrl(detail.verification_id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open original PDF
                  </a>
                )}
              </div>
              <ResultBody fields={detail.result.fields.map(toFieldView)} density="table" />
            </>
          )}
        </div>
      )}
    </>
  );
}
