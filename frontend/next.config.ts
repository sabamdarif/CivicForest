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
  images: {
    // Product/brand imagery is served by the Django API / object storage.
    remotePatterns: [
      { protocol: "https", hostname: apiHost },
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
      { protocol: "http", hostname: "backend" },
    ],
  },
};

export default nextConfig;
