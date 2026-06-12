import { useMemo, useState } from "react";
import type { BatchItem, BatchResponse, Status } from "../types";
import { Report } from "./Report";
import { StatusPill } from "./StatusPill";

type SortKey = "filename" | "brand_name" | "product_type" | "overall" | "processing_ms";
type Filter = "ALL" | "PASS" | "FLAG" | "FAIL" | "ERROR";

const OVERALL_RANK: Record<string, number> = { FAIL: 0, FLAG: 1, PASS: 2, INFO: 3, NOT_CHECKED: 4, ERROR: 5 };

export function BatchResults({ data }: { data: BatchResponse }) {
  const [sortKey, setSortKey] = useState<SortKey>("overall");
  const [asc, setAsc] = useState(true);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [open, setOpen] = useState<number | null>(null);

  const rows = useMemo(() => {
    const filtered = data.items.filter((it) => filter === "ALL" || it.overall === filter);
    const sorted = [...filtered].sort((a, b) => cmp(a, b, sortKey));
    return asc ? sorted : sorted.reverse();
  }, [data.items, filter, sortKey, asc]);

  const s = data.summary;

  function sortBy(key: SortKey) {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(true);
    }
  }

  return (
    <section className="report" aria-label="Batch results">
      <div className="batch-summary">
        <FilterChip label="All" n={s.total} active={filter === "ALL"} on={() => setFilter("ALL")} />
        <FilterChip label="Pass" n={s.PASS} active={filter === "PASS"} on={() => setFilter("PASS")} tone="pass" />
        <FilterChip label="Flag" n={s.FLAG} active={filter === "FLAG"} on={() => setFilter("FLAG")} tone="flag" />
        <FilterChip label="Fail" n={s.FAIL} active={filter === "FAIL"} on={() => setFilter("FAIL")} tone="fail" />
        {s.ERROR > 0 && (
          <FilterChip label="Errors" n={s.ERROR} active={filter === "ERROR"} on={() => setFilter("ERROR")} tone="fail" />
        )}
        <button className="btn-secondary csv-btn" onClick={() => downloadCsv(data.items)}>
          ⭳ Export CSV
        </button>
      </div>

      <table className="fields batch-table">
        <caption className="sr-only">Batch verification results, sortable by column</caption>
        <thead>
          <tr>
            <th scope="col" aria-hidden="true"></th>
            <SortHeader label="File" k="filename" sortKey={sortKey} asc={asc} on={sortBy} />
            <SortHeader label="Brand" k="brand_name" sortKey={sortKey} asc={asc} on={sortBy} />
            <SortHeader label="Type" k="product_type" sortKey={sortKey} asc={asc} on={sortBy} />
            <SortHeader label="Result" k="overall" sortKey={sortKey} asc={asc} on={sortBy} />
            <th scope="col">Checks</th>
            <SortHeader label="Time" k="processing_ms" sortKey={sortKey} asc={asc} on={sortBy} />
          </tr>
        </thead>
        <tbody>
          {rows.map((it) => {
            const idx = data.items.indexOf(it);
            const expanded = open === idx;
            return (
              <BatchRow key={`${it.filename}-${idx}`} it={it} expanded={expanded} onToggle={() => setOpen(expanded ? null : idx)} />
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function BatchRow({ it, expanded, onToggle }: { it: BatchItem; expanded: boolean; onToggle: () => void }) {
  const drillable = !!it.result;
  return (
    <>
      <tr className={expanded ? "row-open" : ""}>
        <td className="cell-expand">
          {drillable && (
            <button
              className="expand-btn"
              aria-expanded={expanded}
              aria-label={expanded ? "Hide details" : "Show details"}
              onClick={onToggle}
            >
              {expanded ? "▾" : "▸"}
            </button>
          )}
        </td>
        <th scope="row" className="field-name">
          {it.filename}
          {it.ttb_id && <span className="ttb-sub">{it.ttb_id}</span>}
        </th>
        <td>{it.brand_name ?? <span className="muted">—</span>}</td>
        <td>{it.product_type ?? <span className="muted">—</span>}</td>
        <td>
          {it.error ? <StatusPill status="FAIL" /> : <StatusPill status={it.overall as Status} />}
          {it.error && <p className="reason">{it.error}</p>}
        </td>
        <td className="counts">
          {it.counts.pass > 0 && <span className="c-pass">{it.counts.pass}✓</span>}
          {it.counts.flag > 0 && <span className="c-flag">{it.counts.flag}⚠</span>}
          {it.counts.fail > 0 && <span className="c-fail">{it.counts.fail}✕</span>}
        </td>
        <td className="cell-time">{it.processing_ms != null ? `${(it.processing_ms / 1000).toFixed(1)}s` : "—"}</td>
      </tr>
      {expanded && it.result && (
        <tr className="drill-row">
          <td colSpan={7}>
            <Report
              data={{ result: it.result, claimed: it.claimed, images: [], form_version: it.form_version, provider: "" }}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function SortHeader({
  label,
  k,
  sortKey,
  asc,
  on,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  asc: boolean;
  on: (k: SortKey) => void;
}) {
  const active = sortKey === k;
  return (
    <th scope="col" aria-sort={active ? (asc ? "ascending" : "descending") : "none"}>
      <button className="sort-btn" onClick={() => on(k)}>
        {label} <span aria-hidden="true">{active ? (asc ? "▲" : "▼") : "⇅"}</span>
      </button>
    </th>
  );
}

function FilterChip({
  label,
  n,
  active,
  on,
  tone,
}: {
  label: string;
  n: number;
  active: boolean;
  on: () => void;
  tone?: "pass" | "flag" | "fail";
}) {
  return (
    <button className={`filter-chip ${active ? "chip-active" : ""} ${tone ? `chip-${tone}` : ""}`} aria-pressed={active} onClick={on}>
      {label} <strong>{n}</strong>
    </button>
  );
}

function cmp(a: BatchItem, b: BatchItem, key: SortKey): number {
  if (key === "overall") return OVERALL_RANK[a.overall] - OVERALL_RANK[b.overall];
  if (key === "processing_ms") return (a.processing_ms ?? 0) - (b.processing_ms ?? 0);
  return String(a[key] ?? "").localeCompare(String(b[key] ?? ""));
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
