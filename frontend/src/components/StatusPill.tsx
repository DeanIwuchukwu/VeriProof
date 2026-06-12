import type { DisplayStatus } from "../types";

// Status is conveyed by icon + text + color together, never color alone (Section 508).
const META: Record<DisplayStatus, { icon: string; label: string; cls: string }> = {
  PASS: { icon: "PASS", label: "Pass", cls: "pill pill-pass" },
  FLAG: { icon: "FLAG", label: "Flag", cls: "pill pill-flag" },
  FAIL: { icon: "FAIL", label: "Fail", cls: "pill pill-fail" },
  ERROR: { icon: "ERR", label: "Error", cls: "pill pill-fail" },
  INFO: { icon: "INFO", label: "Info", cls: "pill pill-info" },
  NOT_CHECKED: { icon: "NC", label: "Not checked", cls: "pill pill-muted" },
};

export function StatusPill({ status }: { status: DisplayStatus }) {
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
