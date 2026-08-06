// Playwright E2E (plan.md §12). Runs the whole stack without Docker:
//   Django (config.settings.e2e, SQLite, fake Razorpay)  → http://localhost:8001
//   Next.js dev server                                    → http://localhost:3001
// Run: npm run e2e
import { defineConfig } from "@playwright/test";

const API = "http://localhost:8001";
const WEB = "http://localhost:3001";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1, // one shared SQLite backend — keep tests serialized
  reporter: [["list"]],
  use: {
    baseURL: WEB,
    channel: "chrome", // system Chrome — no Playwright browser download needed
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        'bash -c "cd ../backend && uv run python manage.py migrate && uv run python manage.py seed_catalog && uv run python manage.py runserver 127.0.0.1:8001 --noreload"',
      url: `${API}/api/v1/categories`,
      reuseExistingServer: true,
      timeout: 180_000,
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings.e2e",
        DJANGO_SECRET_KEY: "e2e-secret-key",
        HEALTH_CHECK_TOKEN: "e2e-health-token",
      },
    },
    {
      // --webpack is Next 16's replacement for the removed --no-turbo flag.
      command: "npx next dev -p 3001 --webpack",
      url: WEB,
      reuseExistingServer: true,
      timeout: 180_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: API,
        INTERNAL_API_BASE_URL: API,
        NEXT_DISABLE_DEV_FILE_SYSTEM_CACHE: "1",
      },
    },
  ],
});
