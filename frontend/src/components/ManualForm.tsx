import { useId, useRef, useState } from "react";
import type { ManualFields } from "../types";

const EMPTY: ManualFields = {
  brand_name: "",
  fanciful_name: "",
  class_type: "",
  source: "",
  alcohol_content: "",
  net_contents: "",
  producer: "",
};

// Source drives the country-of-origin check (required iff IMPORTED). Blank → the
// backend treats it as UNKNOWN and reports country of origin as NOT_CHECKED.
const SOURCE_OPTS = [
  { value: "", label: "— Select —" },
  { value: "domestic", label: "Domestic" },
  { value: "imported", label: "Imported" },
];

export function ManualForm({
  onVerify,
  busy,
}: {
  onVerify: (fields: ManualFields, images: File[]) => void;
  busy: boolean;
}) {
  const [fields, setFields] = useState<ManualFields>(EMPTY);
  const [images, setImages] = useState<File[]>([]);
  const imgRef = useRef<HTMLInputElement>(null);
  const fid = useId();

  const set = (k: keyof ManualFields, v: string) => setFields((f) => ({ ...f, [k]: v }));
  const input = (k: keyof ManualFields, label: string, placeholder = "") => (
    <div className="field-group">
      <label htmlFor={`${fid}-${k}`}>{label}</label>
      <input id={`${fid}-${k}`} value={fields[k]} placeholder={placeholder} onChange={(e) => set(k, e.target.value)} />
    </div>
  );
  const select = (k: keyof ManualFields, label: string, opts: { value: string; label: string }[]) => (
    <div className="field-group">
      <label htmlFor={`${fid}-${k}`}>{label}</label>
      <select id={`${fid}-${k}`} value={fields[k]} onChange={(e) => set(k, e.target.value)}>
        {opts.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <>
      <p className="desc">Type the application values; the label image(s) are read from the file you attach.</p>

      <div className="fields-col">
        {input("brand_name", "BRAND NAME", "CASCADE WINERY")}
        {input("fanciful_name", "FANCIFUL NAME", "CASCADE VAL")}
        {input("class_type", "CLASS / TYPE", "TABLE RED WINE")}
        {select("source", "SOURCE", SOURCE_OPTS)}
        <div className="field-row-2">
          {input("alcohol_content", "ALCOHOL %", "11.5")}
          {input("net_contents", "NET CONTENTS", "750 mL")}
        </div>
        {input("producer", "PRODUCER / BOTTLER", "CASCADE WINERY")}

        <button type="button" className="dropzone compact" onClick={() => imgRef.current?.click()}>
          <span>
            <strong className="dropzone-strong">Attach label image(s)</strong> or drag them here
          </span>
        </button>
        <input
          ref={imgRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          aria-label="Attach label image(s)"
          onChange={(e) => setImages(Array.from(e.target.files ?? []))}
        />
        {images.length > 0 && (
          <span className="file-size" aria-live="polite">
            {images.length} image{images.length > 1 ? "s" : ""} attached
          </span>
        )}
      </div>

      <button className="btn-primary" disabled={!images.length || busy} onClick={() => onVerify(fields, images)}>
        {busy ? "Reading label…" : "Verify label"}
      </button>
    </>
  );
}
