import type { NextConfig } from "next";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.civicforest.local";
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
      { protocol: "http", hostname: "backend" },
      // Local E2E (Playwright) runs the API on plain http://localhost.
      { protocol: "http", hostname: "localhost" },
    ],
  },
};

export default nextConfig;
