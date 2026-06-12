import { useId, useState } from "react";
import type { ManualFields } from "../types";

const EMPTY: ManualFields = {
  brand_name: "",
  fanciful_name: "",
  product_type: "",
  source: "",
  net_contents: "",
  alcohol_content: "",
  class_type: "",
  producer: "",
  country_of_origin: "",
};

export function ManualForm({
  onVerify,
  busy,
}: {
  onVerify: (fields: ManualFields, images: File[]) => void;
  busy: boolean;
}) {
  const [fields, setFields] = useState<ManualFields>(EMPTY);
  const [images, setImages] = useState<File[]>([]);
  const fid = useId();

  function set<K extends keyof ManualFields>(key: K, value: string) {
    setFields((f) => ({ ...f, [key]: value }));
  }

  const text = (key: keyof ManualFields, label: string, placeholder = "") => (
    <div className="field-group">
      <label htmlFor={`${fid}-${key}`}>{label}</label>
      <input
        id={`${fid}-${key}`}
        type="text"
        value={fields[key]}
        placeholder={placeholder}
        onChange={(e) => set(key, e.target.value)}
      />
    </div>
  );

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        if (images.length) onVerify(fields, images);
      }}
    >
      <p className="panel-help">
        Enter the values the application claims, then upload the label image(s). Leave fields blank
        to just read the label and check the mandatory items (warning, required fields, proof).
      </p>

      <div className="grid">
        {text("brand_name", "Brand name", "e.g. OLD TOM DISTILLERY")}
        {text("fanciful_name", "Fanciful name (if any)")}
        <div className="field-group">
          <label htmlFor={`${fid}-pt`}>Product type</label>
          <select id={`${fid}-pt`} value={fields.product_type} onChange={(e) => set("product_type", e.target.value)}>
            <option value="">—</option>
            <option value="distilled spirits">Distilled spirits</option>
            <option value="wine">Wine</option>
            <option value="malt beverage">Malt beverage</option>
          </select>
        </div>
        <div className="field-group">
          <label htmlFor={`${fid}-src`}>Source</label>
          <select id={`${fid}-src`} value={fields.source} onChange={(e) => set("source", e.target.value)}>
            <option value="">—</option>
            <option value="domestic">Domestic</option>
            <option value="imported">Imported</option>
          </select>
        </div>
        {text("alcohol_content", "Alcohol content", "e.g. 45")}
        {text("net_contents", "Net contents", "e.g. 750 mL (comma-separate sizes)")}
        {text("class_type", "Class / type", "e.g. Bourbon Whiskey")}
        {text("producer", "Producer / bottler")}
        {text("country_of_origin", "Country of origin (imports)")}
      </div>

      <div className="field-group">
        <label htmlFor={`${fid}-img`}>Label image(s)</label>
        <input
          id={`${fid}-img`}
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => setImages(Array.from(e.target.files ?? []))}
        />
        {images.length > 0 && (
          <p className="filename" aria-live="polite">
            {images.length} image{images.length > 1 ? "s" : ""} selected
          </p>
        )}
      </div>

      <button type="submit" className="btn-primary" disabled={!images.length || busy}>
        {busy ? "Verifying…" : "Verify label"}
      </button>
    </form>
  );
}
