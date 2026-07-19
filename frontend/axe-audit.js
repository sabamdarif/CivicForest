// Axe a11y audit of the main pages (plan.md §12). Run: node axe-audit.js
// Requires: npm install --save-dev axe-core puppeteer
import { AxePuppeteer } from "@axe-core/puppeteer";
import puppeteer from "puppeteer";

const PAGES = [
  { name: "Home", path: "/" },
  { name: "Shop", path: "/shop" },
  { name: "Product detail", path: "/product/classic-black-tee" },
  { name: "Search results", path: "/search?q=tee" },
  { name: "Login", path: "/login" },
  { name: "Cart", path: "/cart" },
];

const BASE = process.env.WEB_URL || "http://localhost:3000";

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "/usr/bin/google-chrome-stable",
  });
  const page = await browser.newPage();
  let totalViolations = 0;

  for (const { name, path } of PAGES) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle2" });
    const results = await new AxePuppeteer(page).analyze();

    console.log(`\n=== ${name} (${path}) ===`);
    if (results.violations.length === 0) {
      console.log("✓ No violations");
    } else {
      totalViolations += results.violations.length;
      results.violations.forEach((v) => {
        console.log(`  ✗ ${v.id}: ${v.help} (${v.nodes.length} nodes)`);
        console.log(`    Impact: ${v.impact}, WCAG: ${v.tags.filter((t) => t.startsWith("wcag")).join(", ")}`);
      });
    }
  }

  await browser.close();

  console.log(`\n=== Summary ===`);
  console.log(`${totalViolations} total violations across ${PAGES.length} pages.`);
  if (totalViolations > 0) {
    console.log("See detailed violations above. Address critical/serious impacts first.");
  }
})();
