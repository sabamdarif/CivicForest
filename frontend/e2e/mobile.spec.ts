import { test, expect } from "@playwright/test";

test.use({
  viewport: { width: 375, height: 667 }, // iPhone SE dimensions
});

test("mobile header menu navigation drawer opens and navigates", async ({ page }) => {
  await page.goto("/");

  // Verify desktop navigation links are hidden on mobile
  const desktopNav = page.locator("header nav");
  await expect(desktopNav).toBeHidden();

  // Find hamburger menu button and click it
  const menuButton = page.locator('button[aria-label="Open menu"]');
  await expect(menuButton).toBeVisible();
  await menuButton.click();

  // Verify mobile navigation dialog opens
  const mobileNav = page.locator('div[role="dialog"][aria-label="Navigation Menu"]');
  await expect(mobileNav).toBeVisible();

  // Check navigation links inside mobile menu
  await expect(mobileNav.getByRole("link", { name: "Shop", exact: true })).toBeVisible();
  await expect(mobileNav.getByRole("link", { name: "Collections", exact: true })).toBeVisible();

  // Click Shop link in mobile nav
  await mobileNav.getByRole("link", { name: "Shop", exact: true }).click();
  await expect(page).toHaveURL(/\/shop/);
});

test("mobile shop filter drawer opens and applies filters", async ({ page }) => {
  await page.goto("/shop");

  // Verify desktop sidebar filters are hidden on mobile
  const desktopSidebar = page.locator(".hidden.lg\\:block");
  await expect(desktopSidebar).toBeHidden();

  // Click mobile filter button
  const filterButton = page.getByRole("button", { name: /filters/i });
  await expect(filterButton).toBeVisible();
  await filterButton.click();

  // Verify mobile filter drawer opens
  const filterDrawer = page.locator('aside[role="dialog"][aria-label="Filter products"]');
  await expect(filterDrawer).toBeVisible();

  // Click T-Shirts category inside filter drawer
  await filterDrawer.getByRole("button", { name: "T-Shirts" }).click();
  await expect(page).toHaveURL(/category=t-shirts/);

  // Close filter drawer
  await filterDrawer.getByRole("button", { name: "Show Results" }).click();
  await expect(filterDrawer).toBeHidden();
});
