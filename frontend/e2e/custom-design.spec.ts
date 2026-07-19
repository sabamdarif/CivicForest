import { expect, test } from "@playwright/test";

import { TINY_PNG, signup, uniqueEmail } from "./helpers";

test("custom design upload from the product page", async ({ page }) => {
  await signup(page, uniqueEmail("designer"));

  await page.goto("/product/classic-black-tee");
  // The upload needs a concrete variant — pick a size (colour is preselected).
  await page.getByRole("button", { name: "M", exact: true }).click();

  await page.getByRole("button", { name: /Add your own design/ }).click();
  await page
    .locator('input[type="file"]')
    .setInputFiles({ name: "art.png", mimeType: "image/png", buffer: TINY_PNG });
  await page.getByRole("button", { name: "Upload design" }).click();

  await expect(page.getByRole("status")).toContainText("Design uploaded", {
    timeout: 20_000,
  });
});
