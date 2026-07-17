// Sentry (Node/server) — no-op unless NEXT_PUBLIC_SENTRY_DSN is set, so local dev and
// CI builds run untouched. Loaded from instrumentation.ts.
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1"),
    // Don't ship user PII to Sentry (DPDP Act — plan.md §12).
    sendDefaultPii: false,
  });
}
