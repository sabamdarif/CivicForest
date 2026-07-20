"use client";

import Link from "next/link";
import { useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { requestPasswordReset } from "@/lib/auth/allauth";

export default function PasswordResetPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    // Always show the same confirmation — never reveal whether an account exists
    // (plan.md §12). Errors are swallowed for the same reason.
    await requestPasswordReset(email).catch(() => {});
    setSent(true);
    setLoading(false);
  }

  return (
    <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
      <div className="w-full max-w-md rounded-md bg-cream p-8 shadow-card">
        <h1 className="font-serif text-3xl text-ink">Reset your password</h1>
        {sent ? (
          <p className="mt-4 text-sm text-ink/70">
            If an account exists for <span className="font-medium text-ink">{email}</span>, we&apos;ve
            sent a link to reset your password. Check your inbox.
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm text-ink/60">
              Enter your email and we&apos;ll send you a reset link.
            </p>
            <form onSubmit={onSubmit} className="mt-7 space-y-5">
              <div>
                <label htmlFor="email" className="text-sm font-medium text-ink">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  className="input-field mt-1.5"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="btn-dark w-full justify-center disabled:opacity-60"
              >
                <span className="text-gold">{loading ? "Sending…" : "Send reset link"}</span>
                {!loading && <ArrowRight className="h-4 w-4 text-gold" />}
              </button>
            </form>
          </>
        )}
        <p className="mt-6 text-center text-sm text-ink/60">
          <Link href="/login" className="font-semibold text-gold hover:underline">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
}
