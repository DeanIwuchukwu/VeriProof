import type { ManualFields, VerifyResponse } from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function postForm(path: string, body: FormData): Promise<VerifyResponse> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method: "POST", body });
  } catch {
    throw new Error("Could not reach the verification service. Is the backend running?");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail || `Verification failed (HTTP ${res.status}).`);
  }
  return (await res.json()) as VerifyResponse;
}

export function verifyCola(file: File): Promise<VerifyResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return postForm("/api/verify/cola", fd);
}

export function verifyManual(fields: ManualFields, images: File[]): Promise<VerifyResponse> {
  const fd = new FormData();
  for (const img of images) fd.append("images", img);
  (Object.keys(fields) as (keyof ManualFields)[]).forEach((k) => {
    if (fields[k]) fd.append(k, fields[k]);
  });
  return postForm("/api/verify/manual", fd);
}
