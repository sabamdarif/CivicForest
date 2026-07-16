"use client";

// Thin wrapper around allauth's headless browser endpoints (plan.md §5). Auth state
// lives in Django's session cookie — never in JS-accessible storage — so this client
// just orchestrates fetches and echoes the CSRF token on mutations.

import { apiBase } from "@/lib/api/client";

const ALLAUTH = () => `${apiBase()}/_allauth/browser/v1`;

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${ALLAUTH()}${path}`, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      // Django's CSRF cookie is not HttpOnly by design so JS can echo it back.
      ...(method !== "GET" ? { "X-CSRFToken": getCookie("csrftoken") ?? "" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = (await res.json().catch(() => ({}))) as T & {
    errors?: { message: string }[];
  };
  if (!res.ok) {
    const message = data?.errors?.[0]?.message ?? `Request failed (${res.status})`;
    throw new AuthError(res.status, message);
  }
  return data as T;
}

export class AuthError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export interface SessionUser {
  id: string | number;
  email?: string;
  display?: string;
}

export interface SessionResponse {
  status: number;
  data?: { user?: SessionUser };
  meta?: { is_authenticated: boolean };
}

/** Prime the CSRF cookie and read current auth state. Call before any mutation. */
export async function getSession(): Promise<SessionResponse> {
  try {
    return await request<SessionResponse>("/auth/session", "GET");
  } catch (err) {
    if (err instanceof AuthError && err.status === 401) {
      return { status: 401, meta: { is_authenticated: false } };
    }
    throw err;
  }
}

export async function login(email: string, password: string): Promise<SessionResponse> {
  // Ensure the csrftoken cookie exists before POSTing.
  await getSession();
  return request<SessionResponse>("/auth/login", "POST", { email, password });
}

export async function signup(email: string, password: string): Promise<SessionResponse> {
  // Prime the csrftoken cookie before POSTing (same as login).
  await getSession();
  return request<SessionResponse>("/auth/signup", "POST", { email, password });
}

/** Kick off the password-reset email flow. allauth always returns 200 here so the
 * response never reveals whether an account exists (plan.md §12). */
export async function requestPasswordReset(email: string): Promise<void> {
  await getSession();
  await request("/auth/password/request", "POST", { email });
}

export async function logout(): Promise<void> {
  await request("/auth/session", "DELETE");
}

/** Redirect the browser into allauth's provider flow (Google/Apple).
 * Guarded for SSR/prerender where `window` is undefined — the correct callback
 * origin is filled in on the client after hydration. */
export function socialLoginUrl(provider: "google" | "apple"): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const callback = encodeURIComponent(`${origin}/account`);
  return `${ALLAUTH()}/auth/provider/redirect?provider=${provider}&callback_url=${callback}&process=login`;
}
