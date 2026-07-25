"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EmailOtpForm } from "@/components/account/EmailOtpForm";
import {
  getCurrentUser,
  updateCurrentUser,
} from "@/lib/api/account";
import { ApiError } from "@/lib/api/client";
import type { CurrentUser } from "@/lib/api/types";
import {
  AuthError,
  changeEmail,
  getSession,
  resendEmailVerification,
} from "@/lib/auth/allauth";

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [form, setForm] = useState({ first_name: "", last_name: "", phone: "" });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Email change flow: idle → editing (enter new email) → verifying (enter code)
  const [emailStep, setEmailStep] = useState<"idle" | "editing" | "verifying">("idle");
  const [newEmail, setNewEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);

  useEffect(() => {
    getSession()
      .then((s) => {
        if (!s.meta?.is_authenticated) {
          router.replace("/login");
          return;
        }
        return getCurrentUser();
      })
      .then((u) => {
        if (u) {
          setUser(u);
          setForm({ first_name: u.first_name, last_name: u.last_name, phone: u.phone });
        }
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function onSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      setUser(await updateCurrentUser(form));
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  async function onRequestEmailChange(e: React.FormEvent) {
    e.preventDefault();
    setEmailError(null);
    try {
      await changeEmail(newEmail);
      setEmailStep("verifying");
    } catch (err) {
      setEmailError(
        err instanceof AuthError ? err.message : "Could not start the email change.",
      );
    }
  }

  if (!user) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  return (
    <div className="container-page max-w-2xl py-16">
      <p className="eyebrow">My Account</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">Edit profile</h1>

      <form onSubmit={onSaveProfile} className="mt-10 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">First name</span>
            <input
              type="text"
              value={form.first_name}
              autoComplete="given-name"
              onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
              className="input-field mt-1.5"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">Last name</span>
            <input
              type="text"
              value={form.last_name}
              autoComplete="family-name"
              onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
              className="input-field mt-1.5"
            />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">Phone</span>
          <input
            type="tel"
            value={form.phone}
            autoComplete="tel"
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            className="input-field mt-1.5"
          />
        </label>

        {error && (
          <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        {saved && <p className="text-sm text-ink/60">Profile saved.</p>}

        <button type="submit" disabled={busy} className="btn-dark disabled:opacity-60">
          {busy ? "Saving…" : "Save changes"}
        </button>
      </form>

      <section className="mt-14 border-t border-black/10 pt-10">
        <h2 className="font-serif text-2xl text-ink">Email address</h2>
        <p className="mt-2 text-sm text-ink/60">
          Signed in as <span className="font-semibold text-ink">{user.email}</span>. Changing
          it requires verifying the new address with an emailed code.
        </p>

        {emailStep === "idle" && (
          <button
            type="button"
            onClick={() => {
              setNewEmail("");
              setEmailError(null);
              setEmailStep("editing");
            }}
            className="btn-outline mt-5"
          >
            Change email
          </button>
        )}

        {emailStep === "editing" && (
          <form onSubmit={onRequestEmailChange} className="mt-5 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-ink">New email address</span>
              <input
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="input-field mt-1.5"
              />
            </label>
            {emailError && (
              <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                {emailError}
              </p>
            )}
            <div className="flex items-center gap-4">
              <button type="submit" className="btn-dark">
                Send code
              </button>
              <button
                type="button"
                onClick={() => setEmailStep("idle")}
                className="text-sm text-ink/60 hover:text-ink"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {emailStep === "verifying" && (
          <div className="mt-5">
            <EmailOtpForm
              email={newEmail}
              onResend={() => resendEmailVerification(newEmail)}
              onVerified={async () => {
                setEmailStep("idle");
                setUser(await getCurrentUser().catch(() => user));
              }}
            />
          </div>
        )}
      </section>
    </div>
  );
}
