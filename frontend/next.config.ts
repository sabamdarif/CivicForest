import type { NextConfig } from "next";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.civicforest.local";
const isProduction = process.env.NODE_ENV === "production";
const apiOrigin = (() => {
  try {
    return new URL(apiBase).origin;
  } catch {
    return "https://api.civicforest.local";
  }
})();
const apiHost = (() => {
  try {
    return new URL(apiBase).hostname;
  } catch {
    return "api.civicforest.local";
  }
})();

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Dev is served through Caddy at civicforest.local; without this Next blocks
  // all /_next/* dev assets cross-origin and the page never hydrates.
  allowedDevOrigins: ["civicforest.local", "api.civicforest.local"],
  // A stray lockfile in $HOME makes Next infer the wrong workspace root.
  turbopack: { root: __dirname },
  images: {
    // Product/brand imagery is served by the Django API / object storage.
    remotePatterns: [
      { protocol: "https", hostname: apiHost },
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
      ...(!isProduction
        ? [
            { protocol: "http" as const, hostname: "backend" },
            // Local E2E (Playwright) runs the API on plain http://localhost.
            { protocol: "http" as const, hostname: "localhost" },
          ]
        : []),
    ],
  },
  async headers() {
    const contentSecurityPolicy = [
      "default-src 'self'",
      `script-src 'self'${isProduction ? "" : " 'unsafe-eval'"} https://checkout.razorpay.com https://cdn.razorpay.com`,
      "frame-src https://api.razorpay.com https://checkout.razorpay.com",
      `connect-src 'self' ${apiOrigin} https://lumberjack.razorpay.com`,
      "img-src 'self' data: https:",
      "style-src 'self' 'unsafe-inline'",
      "font-src 'self' data:",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; ");

    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(self), geolocation=()",
          },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
        ],
      },
    ];
  },
};

export default nextConfig;
