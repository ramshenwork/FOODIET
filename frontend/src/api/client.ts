// The only module that calls the backend. Handles cookies, CSRF, one silent refresh, and error shapes.
import type { ApiErrorBody, Paywall } from "./types";

const BASE = "/api/v1";
const SAFE = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
    public paywall?: Paywall,
    public fields?: { field: string; message: string }[],
  ) {
    super(message);
  }
  get isPaywall() { return this.status === 402; }
  get isOffline() { return this.code === "offline"; }
}

function csrf(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!csrf()) return false; // never signed in on this browser: nothing to refresh
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() },
  }).then((r) => r.ok).catch(() => false).finally(() => { setTimeout(() => (refreshing = null), 0); });
  return refreshing;
}

export async function api<T>(path: string, init: { method?: string; body?: unknown; form?: FormData; idempotencyKey?: string } = {}): Promise<T> {
  const method = init.method ?? "GET";
  const send = () => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    if (!SAFE.has(method)) headers["X-CSRF-Token"] = csrf();
    if (init.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;
    return fetch(`${BASE}${path}`, {
      method, headers, credentials: "same-origin",
      body: init.form ?? (init.body === undefined ? undefined : JSON.stringify(init.body)),
    });
  };

  let res: Response;
  try {
    res = await send();
    if (res.status === 401 && !path.startsWith("/auth/") && (await tryRefresh())) res = await send();
  } catch {
    throw new ApiError(0, "offline", "You seem to be offline.");
  }

  if (res.ok) return (res.status === 204 ? undefined : await res.json()) as T;
  let body: ApiErrorBody | undefined;
  try { body = await res.json(); } catch { /* non-JSON error */ }
  throw new ApiError(
    res.status,
    body?.error.code ?? "http_error",
    body?.error.message ?? "Something went wrong.",
    body?.error.request_id,
    body?.paywall,
    body?.fields,
  );
}
