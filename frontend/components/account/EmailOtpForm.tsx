"use client";

import { useState } from "react";

import { AuthError, verifyEmailCode } from "@/lib/auth/allauth";

/** Entry form for the emailed verification code (OTP). Used by both the signup
 * flow and the change-email flow on /account/profile. */
export function EmailOtpForm({
  email,
  onVerified,
  onResend,
}: {
  email: string;
  onVerified: () => void;
  onResend?: () => Promise<void>;
}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await verifyEmailCode(code.trim());
      onVerified();
    } catch (err) {
      setError(
        err instanceof AuthError ? err.message : "Verification failed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onResendClick() {
    setError(null);
    setNotice(null);
    try {
      await onResend?.();
      setNotice("A new code is on its way.");
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not resend the code.");
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-sm text-ink/70">
        We sent a verification code to <span className="font-semibold text-ink">{email}</span>.
        Enter it below to confirm.
      </p>
      <label className="block">
        <span className="text-sm font-medium text-ink">Verification code</span>
        <input
          type="text"
          required
          autoFocus
          autoComplete="one-time-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="e.g. ABCD-1234"
          className="input-field mt-1.5 uppercase tracking-widest"
        />
      </label>
      {error && (
        <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {notice && <p className="text-sm text-ink/60">{notice}</p>}
      <div className="flex items-center gap-4">
        <button type="submit" disabled={busy} className="btn-dark disabled:opacity-60">
          {busy ? "Verifying…" : "Verify"}
        </button>
        {onResend && (
          <button
            type="button"
            onClick={onResendClick}
            className="text-sm font-semibold text-gold hover:underline"
          >
            Resend code
          </button>
        )}
      </div>
    </form>
  );
}
