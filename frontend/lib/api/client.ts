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

export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { revalidate, ...init } = options;
  const url = path.startsWith("http") ? path : `${apiBase()}/api/v1${path}`;

  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
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
