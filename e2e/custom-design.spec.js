// The custom-design upload round-trip. The designer orchestrates presign -> PUT -> complete; in
// local/dev the presigned URL points at the dev-upload receiver that writes to disk storage, so
// this is a genuine upload through the real path, not a network mock. A real PNG is uploaded and
// the tool should accept it: the preview appears and, once rights are accepted, the add action
// becomes available.

const path = require("path");
const { test, expect } = require("@playwright/test");
const { login } = require("./helpers");

const ART = path.join(__dirname, "fixtures", "art.png");

test("uploading artwork to the designer is accepted end to end", async ({ page }) => {
  await login(page);

  await page.goto("/customise/");
  await page.locator(".blank-card__link").first().click();
  await page.waitForURL("**/customise/**");

  const designer = page.locator("[data-designer]");
  await expect(designer).toBeVisible();

  await designer.locator("[data-upload]").setInputFiles(ART);

  // The upload status flips to "Uploaded" only after presign + dev-upload + complete all return
  // ready, so this one assertion covers the whole round-trip.
  await expect(designer.locator("[data-upload-status]")).toHaveText(/uploaded/i, { timeout: 15000 });

  // The preview is unhidden with the sanitised artwork assigned, confirming the design was
  // accepted. The private designs store is not served over HTTP in dev, so the <img> bytes do
  // not load; the DOM state (unhidden, src set) is the reliable signal, not pixel visibility.
  await expect(designer.locator("[data-art]")).toHaveJSProperty("hidden", false);
  await expect(designer.locator("[data-art]")).toHaveAttribute("src", /designs\/print\//);

  // Accepting the rights declaration unlocks the add-to-cart action.
  await designer.locator("[data-rights]").check();
  await expect(designer.locator("[data-add]")).toBeEnabled();
});
