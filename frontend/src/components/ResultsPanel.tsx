import type { VerifyResponse } from "../types";
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
  const images = data.images.map((i) => i.image_type || "label").join(", ");

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
        />
        <button type="button" className="btn-reject" onClick={() => {}}>
          ✕ Reject
        </button>
        <button type="button" className="btn-accept" onClick={() => {}}>
          ✓ Accept
        </button>
      </div>

      <div className="meta-footer">
        {data.claimed?.ttb_id && (
          <span className="meta-stack">
            <span className="meta-label">TTB ID</span>
            <span className="meta-val">{data.claimed.ttb_id}</span>
          </span>
        )}
        {images && (
          <span className="meta-stack">
            <span className="meta-label">LABEL IMAGES</span>
            <span className="meta-val">{images}</span>
          </span>
        )}
        {data.form_version && (
          <span className="meta-stack">
            <span className="meta-label">FORM</span>
            <span className="meta-val">{data.form_version}</span>
          </span>
        )}
        <span className="meta-disclaimer">
          Type size, characters-per-inch, and contrasting-background checks are outside COLA
          certification scope and not evaluated here.
        </span>
      </div>
    </>
  );
}
