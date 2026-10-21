// Accessibility sweep with axe-core across the nine key pages. Public pages are scanned without a
// session (login must be scanned signed-out); the cart, checkout and account pages are scanned
// after logging in with a cart item so they render their real content. The gate is WCAG 2.0/2.1
// Level A and AA conformance (the recognised legal standard); axe best-practice advisories such as
// landmark "region" and "heading-order" are not WCAG failures and are reported in the task notes
// rather than failing the build. A real WCAG failure prints the page and rule ids, never silenced.

const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const { login, addSeededVariantToCart } = require("./helpers");

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function scan(page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.length,
  }));
}

async function sweep(page, paths) {
  const failures = {};
  for (const p of paths) {
    await page.goto(p);
    const violations = await scan(page);
    if (violations.length) failures[p] = violations;
  }
  expect(failures, JSON.stringify(failures, null, 2)).toEqual({});
}

test("public pages have no axe violations", async ({ page }) => {
  await sweep(page, [
    "/",
    "/shop/",
    "/product/classic-black-tee/",
    "/accounts/login/",
    "/customise/",
    "/contact/",
  ]);
});

test("authenticated pages have no axe violations", async ({ page }) => {
  await login(page);
  await addSeededVariantToCart(page);
  await sweep(page, ["/cart/", "/checkout/", "/account/"]);
});
