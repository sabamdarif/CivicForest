"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { AuthError, login, socialLoginUrl } from "@/lib/auth/allauth";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/account");
      router.refresh();
    } catch (err) {
      // Generic message — never reveal whether the email exists (plan.md §12).
      setError(
        err instanceof AuthError && err.status === 400
          ? "Incorrect email or password."
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-md bg-cream p-8 shadow-card">
      <h1 className="font-serif text-3xl text-ink">Login to your account</h1>
      <p className="mt-2 text-sm text-ink/60">Welcome back! Please enter your details.</p>

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

        <div>
          <label htmlFor="password" className="text-sm font-medium text-ink">
            Password
          </label>
          <div className="relative mt-1.5">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              className="input-field pr-12"
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute inset-y-0 right-3 text-xs uppercase tracking-wide text-ink/50 hover:text-ink"
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          <div className="mt-2 text-right">
            <Link href="/account/password/reset" className="text-sm text-gold hover:underline">
              Forgot Password?
            </Link>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-ink/70">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 accent-gold"
          />
          Remember me
        </label>

        {error && (
          <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}

        <button type="submit" disabled={loading} className="btn-dark w-full justify-center disabled:opacity-60">
          <span className="text-gold">{loading ? "Logging in…" : "Login"}</span>
          {!loading && <ArrowRight className="text-gold" />}
        </button>
      </form>

      <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wide text-ink/40">
        <span className="h-px flex-1 bg-black/10" />
        or continue with
        <span className="h-px flex-1 bg-black/10" />
      </div>

      <div className="space-y-3">
        <a href={socialLoginUrl("google")} className="btn-outline w-full justify-center gap-3">
          <span className="font-bold text-[#4285F4]">G</span> Continue with Google
        </a>
        <a href={socialLoginUrl("apple")} className="btn-outline w-full justify-center gap-3">
           Continue with Apple
        </a>
      </div>

      <p className="mt-6 text-center text-sm text-ink/60">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-semibold text-gold hover:underline">
          Sign Up
        </Link>
      </p>
    </div>
  );
}
