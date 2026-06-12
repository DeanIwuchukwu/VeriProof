// Mirrors the backend response shape (app/main.py _response).

export type Status = "PASS" | "FLAG" | "FAIL" | "INFO" | "NOT_CHECKED";

export interface FieldVerdict {
  field: string;
  label: string;
  status: Status;
  claimed: string | null;
  extracted: string | null;
  reason: string;
  confidence: number;
  source_image: number | null;
}

export interface VerificationResult {
  fields: FieldVerdict[];
  overall: Status;
  image_quality: string;
  processing_ms: number | null;
  notes: string | null;
}

export interface ClaimedFields {
  ttb_id: string | null;
  serial_number: string | null;
  brand_name: string | null;
  fanciful_name: string | null;
  product_type: string;
  source: string;
  net_contents: string[];
  alcohol_content: string | null;
  class_type_description: string | null;
  applicant_name_address: string | null;
  dba_tradename: string | null;
  formula: string | null;
}

export interface ImageMeta {
  image_type: string | null;
  actual_dimensions: string | null;
  width_px: number;
  height_px: number;
}

export interface VerifyResponse {
  claimed: ClaimedFields | null;
  result: VerificationResult;
  images: ImageMeta[];
  form_version: string | null;
  provider: string;
}

export interface BatchItem {
  filename: string;
  error: string | null;
  ttb_id: string | null;
  brand_name: string | null;
  product_type: string | null;
  overall: Status | "ERROR";
  processing_ms: number | null;
  counts: { pass: number; flag: number; fail: number };
  claimed: ClaimedFields | null;
  result: VerificationResult | null;
  form_version: string | null;
}

export interface BatchResponse {
  items: BatchItem[];
  summary: { total: number; PASS: number; FLAG: number; FAIL: number; ERROR: number };
}

export interface ManualFields {
  brand_name: string;
  fanciful_name: string;
  product_type: string;
  source: string;
  net_contents: string;
  alcohol_content: string;
  class_type: string;
  producer: string;
  country_of_origin: string;
}
