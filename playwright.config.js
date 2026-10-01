// Playwright config for the CivicForest storefront e2e and axe suites.
//
// webServer runs e2e/serve.sh, which migrates, seeds the catalogue and dev users, then serves
// on 127.0.0.1:8000. The suite shares one dev user and one cart, so it runs single-worker to
// avoid cart contention. Chromium only, to keep the run lean.

const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "bash e2e/serve.sh",
    url: "http://127.0.0.1:8000/",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
