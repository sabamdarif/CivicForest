// Next.js server instrumentation hook — loads the right Sentry config per runtime.
// Everything is gated on NEXT_PUBLIC_SENTRY_DSN inside those modules, so this is inert
// when Sentry isn't configured.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export { captureRequestError as onRequestError } from "@sentry/nextjs";
