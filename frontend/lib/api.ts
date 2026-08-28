import type { TokenPair } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL && typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_BASE_URL
    : ""; // in the browser we go through Next rewrites at /api/*

const ACCESS_KEY = "aq.access";
const REFRESH_KEY = "aq.refresh";

export function getAccess(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
}
export function getRefresh(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
}
export function setTokens(t: TokenPair) {
  localStorage.setItem(ACCESS_KEY, t.access_token);
  localStorage.setItem(REFRESH_KEY, t.refresh_token);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

function url(path: string) {
  if (path.startsWith("http")) return path;
  return `${BASE}/api${path.startsWith("/") ? path : `/${path}`}`;
}

async function raw(path: string, init: RequestInit, withAuth: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  if (withAuth) {
    const tok = getAccess();
    if (tok) headers.set("Authorization", `Bearer ${tok}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(url(path), { ...init, headers });
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    const rt = getRefresh();
    if (!rt) return false;
    const res = await raw(
      "/auth/refresh",
      { method: "POST", body: JSON.stringify({ refresh_token: rt }) },
      false,
    );
    if (!res.ok) {
      clearTokens();
      return false;
    }
    setTokens((await res.json()) as TokenPair);
    return true;
  })();
  const out = await refreshing;
  refreshing = null;
  return out;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean; retry?: boolean } = {},
): Promise<T> {
  const withAuth = opts.auth ?? true;
  let res = await raw(path, init, withAuth);

  if (res.status === 401 && withAuth && opts.retry !== false) {
    if (await tryRefresh()) {
      res = await raw(path, init, true);
    }
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function wsUrl(path: string): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  const token = getAccess() ?? "";
  return `${proto}://${host}${path}?token=${encodeURIComponent(token)}`;
}
