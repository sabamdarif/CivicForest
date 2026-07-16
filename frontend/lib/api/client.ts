// Single typed API client wrapping fetch to Django. No component calls fetch
// directly (plan.md §3). Server components use the internal base URL (inside the
// Docker network); browser code uses the public URL.

const PUBLIC_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.civicforest.local";
const INTERNAL_BASE = process.env.INTERNAL_API_BASE_URL ?? PUBLIC_BASE;

const isServer = typeof window === "undefined";

export function apiBase(): string {
  return isServer ? INTERNAL_BASE : PUBLIC_BASE;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type FetchOptions = RequestInit & { revalidate?: number };

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Prime and read Django's CSRF token for browser mutations. Django's
 * SessionAuthentication enforces CSRF on unsafe methods, so every non-GET request
 * from the browser must echo the token from the (non-HttpOnly) cookie. A guest with
 * no session yet won't have the cookie; hitting allauth's session endpoint sets it.
 */
async function ensureCsrfToken(): Promise<string> {
  let token = getCookie("csrftoken");
  if (!token) {
    await fetch(`${apiBase()}/_allauth/browser/v1/auth/session`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    }).catch(() => {});
    token = getCookie("csrftoken");
  }
  return token ?? "";
}

export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { revalidate, ...init } = options;
  const url = path.startsWith("http") ? path : `${apiBase()}/api/v1${path}`;

  const method = (init.method ?? "GET").toUpperCase();
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;

  const headers: Record<string, string> = { Accept: "application/json" };
  // Let the browser set the multipart boundary for FormData bodies.
  if (init.body && !isForm) headers["Content-Type"] = "application/json";
  // CSRF only matters browser-side; server components never mutate.
  if (!isServer && !SAFE_METHODS.has(method)) {
    headers["X-CSRFToken"] = await ensureCsrfToken();
  }
  Object.assign(headers, init.headers);

  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers,
    // ISR for public catalog data; opt out with revalidate: 0.
    ...(revalidate !== undefined ? { next: { revalidate } } : {}),
  });

  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
