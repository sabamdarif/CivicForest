import { expect, test } from "@playwright/test";

import { PASSWORD, signup, uniqueEmail } from "./helpers";

test("signup then login with the new account", async ({ page }) => {
  const email = uniqueEmail("auth");

  await signup(page, email);
  await expect(page).toHaveURL(/\/account/);

  // Fresh session → the same credentials log in through the UI.
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email Address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await page.waitForURL("**/account");
});

test("login with wrong password shows an error, not a session", async ({ page }) => {
  const email = uniqueEmail("badpw");
  await signup(page, email);
  await page.context().clearCookies();

  await page.goto("/login");
  await page.getByLabel("Email Address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("wrong-password-123");
  await page.getByRole("button", { name: "Login", exact: true }).click();

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("alert")).toBeVisible();
});
