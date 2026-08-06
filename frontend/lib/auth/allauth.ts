"use client";

// Thin wrapper around allauth's headless browser endpoints (plan.md §5). Auth state
// lives in Django's session cookie — never in JS-accessible storage — so this client
// just orchestrates fetches and echoes the CSRF token on mutations.

import { apiBase, publicApiBase } from "@/lib/api/client";

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
    throw new AuthError(res.status, message, data);
  }
  return data as T;
}

export class AuthError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Raw allauth response body — carries pending-flow info on 401s. */
    public data?: unknown,
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

export interface AuthFlow {
  id: string;
  is_pending?: boolean;
}

export interface SessionResponse {
  status: number;
  data?: { user?: SessionUser; flows?: AuthFlow[] };
  meta?: { is_authenticated: boolean };
}

/** True when an allauth 401 means "account exists, email verification pending" —
 * i.e. the user must enter the emailed code before the session authenticates. */
export function hasPendingEmailVerification(err: unknown): boolean {
  if (!(err instanceof AuthError) || err.status !== 401) return false;
  const flows = (err.data as SessionResponse | undefined)?.data?.flows;
  return flows?.some((f) => f.id === "verify_email" && f.is_pending) ?? false;
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

/** Start an email change: allauth stages the new address and emails it a
 * verification code (ACCOUNT_CHANGE_EMAIL — the old email stays active until
 * the code is confirmed via verifyEmailCode). */
export async function changeEmail(email: string): Promise<void> {
  await request("/account/email", "POST", { email });
}

/** Confirm an emailed verification code (signup or email change). */
export async function verifyEmailCode(code: string): Promise<void> {
  await request("/auth/email/verify", "POST", { key: code });
}

/** Re-send the verification code for a staged (unverified) email address. */
export async function resendEmailVerification(email: string): Promise<void> {
  await request("/account/email", "PUT", { email });
}

/** Re-send the signup verification code for the pending (unauthenticated) session. */
export async function resendSignupCode(): Promise<void> {
  await request("/auth/email/verify/resend", "POST", {});
}

/** Confirm the password mid-session — unlocks sensitive operations (e.g. editing
 * a saved address) that the API guards with 403 reauthentication_required. */
export async function reauthenticate(password: string): Promise<void> {
  await request("/auth/reauthenticate", "POST", { password });
}

/** Redirect the browser into allauth's provider flow (Google/Apple).
 * Guarded for SSR/prerender where `window` is undefined — the correct callback
 * origin is filled in on the client after hydration. */
/** Browser-only: call from a click handler. Uses the public API base and the real
 * window origin — rendering this into an SSR href causes a hydration mismatch. */
export function socialLoginUrl(
  provider: "google" | "apple",
  callbackPath = "/account",
): string {
  const callback = encodeURIComponent(`${window.location.origin}${callbackPath}`);
  return `${publicApiBase()}/_allauth/browser/v1/auth/provider/redirect?provider=${provider}&callback_url=${callback}&process=login`;
}
