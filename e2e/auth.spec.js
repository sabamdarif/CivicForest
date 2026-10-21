// Auth flows against django-allauth. Email verification is mandatory, so signup does not log the
// user in; it lands on the "check your email" screen. Login as the seeded verified user reaches
// the account dashboard.

const { test, expect } = require("@playwright/test");
const { login } = require("./helpers");

test("signup with a fresh email shows the mandatory verification screen", async ({ page }) => {
  const email = `e2e+${Date.now()}@civicforest.local`;
  await page.goto("/accounts/signup/");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password1"]', "Str0ng!Passw0rd2026");
  await page.fill('input[name="password2"]', "Str0ng!Passw0rd2026");
  await page.locator('form:has(input[name="password1"]) button[type=submit]').click();

  // Mandatory verification: the account is not signed in, so the dashboard is never reached.
  await expect(page.locator("body")).toContainText(/verif/i);
  expect(new URL(page.url()).pathname).not.toBe("/account/");
});

test("login as the seeded verified user reaches the account dashboard", async ({ page }) => {
  await login(page);
  expect(new URL(page.url()).pathname).toBe("/account/");
});
