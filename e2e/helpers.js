// Shared helpers for the e2e suite: logging in as the seeded verified customer and dropping a
// known in-stock variant into the cart through the real product-page form.

const { expect } = require("@playwright/test");

const EMAIL = "test@civicforest.local";
const PASSWORD = "test12345";

// Seeded by seed_catalog. Offset 0, default (first) colour Black, size S has stock, so the
// first non-disabled size radio is always addable.
const SEEDED_PRODUCT_SLUG = "classic-black-tee";
const SEEDED_PRODUCT_NAME = "Classic Black Tee";

async function login(page, email = EMAIL, password = PASSWORD) {
  await page.goto("/accounts/login/");
  await page.fill('input[name="login"]', email);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForURL("**/account/"),
    page.locator("form.auth-form button[type=submit]").click(),
  ]);
}

async function addSeededVariantToCart(page, slug = SEEDED_PRODUCT_SLUG) {
  await page.goto(`/product/${slug}/`);
  await page.locator('input[name="size"]:not([disabled])').first().check({ force: true });
  await Promise.all([
    page.waitForResponse((resp) => resp.url().includes("/cart/add/")),
    page.locator("form.buy__form button[type=submit]").click(),
  ]);
  await page.goto("/cart/");
  await expect(page.locator(".cart__layout")).toContainText(SEEDED_PRODUCT_NAME);
}

module.exports = {
  login,
  addSeededVariantToCart,
  EMAIL,
  PASSWORD,
  SEEDED_PRODUCT_SLUG,
  SEEDED_PRODUCT_NAME,
};
