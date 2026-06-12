import type { Status } from "../types";

// Status is conveyed by icon + text + color together — never color alone (Section 508).
const META: Record<Status, { icon: string; label: string; cls: string }> = {
  PASS: { icon: "✓", label: "Pass", cls: "pill pill-pass" },
  FLAG: { icon: "⚠", label: "Flag", cls: "pill pill-flag" },
  FAIL: { icon: "✕", label: "Fail", cls: "pill pill-fail" },
  INFO: { icon: "ℹ", label: "Info", cls: "pill pill-info" },
  NOT_CHECKED: { icon: "–", label: "Not checked", cls: "pill pill-muted" },
};

export function StatusPill({ status }: { status: Status }) {
  const m = META[status];
  return (
    <span className={m.cls}>
      <span aria-hidden="true" className="pill-icon">
        {m.icon}
      </span>
      {m.label}
    </span>
  );
}
