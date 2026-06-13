import type {
  BatchResponse,
  Decision,
  DecisionAction,
  HistoryChatRequest,
  HistoryChatResponse,
  HistoryDetail,
  HistoryItem,
  ManualFields,
  VerifyResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function postForm<T>(path: string, body: FormData): Promise<T> {
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
  return (await res.json()) as T;
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

export function verifyBatch(files: File[]): Promise<BatchResponse> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  return postForm("/api/verify/batch", fd);
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`);
  } catch {
    throw new Error("Could not reach the verification service. Is the backend running?");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail || `Request failed (HTTP ${res.status}).`);
  }
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Could not reach the verification service. Is the backend running?");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail || `Request failed (HTTP ${res.status}).`);
  }
  return (await res.json()) as T;
}

/** Saved verifications, newest first, each with its latest decision. */
export function listVerifications(): Promise<{ items: HistoryItem[] }> {
  return getJson("/api/verifications");
}

/** One saved verification with its full field report and all decisions. */
export function getVerificationDetail(id: string): Promise<HistoryDetail> {
  return getJson(`/api/verifications/${id}`);
}

export function historyChat(body: HistoryChatRequest): Promise<HistoryChatResponse> {
  return postJson("/api/history/chat", body);
}

/** URL of the stored original COLA PDF. */
export function pdfUrl(id: string): string {
  return `${BASE}/api/verifications/${id}/pdf`;
}

/** Permanently remove a saved verification (and its decisions). */
export async function deleteVerification(id: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/verifications/${id}`, { method: "DELETE" });
  } catch {
    throw new Error("Could not reach the verification service. Is the backend running?");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail || `Delete failed (HTTP ${res.status}).`);
  }
}

/** Record a reviewer decision (append-only on the server; the latest wins). */
export async function submitDecision(
  verificationId: string,
  action: DecisionAction,
  note?: string,
): Promise<Decision> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/verifications/${verificationId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, note: note || null }),
    });
  } catch {
    throw new Error("Could not reach the verification service. Is the backend running?");
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(data?.detail || `Saving the decision failed (HTTP ${res.status}).`);
  }
  return (await res.json()) as Decision;
}
