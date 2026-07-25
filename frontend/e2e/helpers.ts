import { type Page } from "@playwright/test";

export const API = "http://localhost:8001";
export const WEBHOOK_SECRET = "e2e-webhook-secret"; // must match config/settings/e2e.py
export const PASSWORD = "e2e-Str0ng-pass!";

export function uniqueEmail(tag: string): string {
  return `${tag}-${Date.now()}@e2e.test`;
}

/** Sign up a fresh account through the real UI; lands on /account. */
export async function signup(page: Page, email: string): Promise<void> {
  await page.goto("/signup");
  // exact — the footer newsletter input is also labelled "Email address"
  await page.getByLabel("Email Address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign Up" }).click();
  await page.waitForURL("**/account");
}

/** Minimal valid 1×1 PNG for upload tests (server re-encodes it anyway). */
export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

/** Fake Razorpay hosted-checkout script: immediately "pays" and calls the handler. */
export const FAKE_RAZORPAY_JS = `
  window.Razorpay = function (options) {
    window.__rzpOptions = options;
    return {
      open: function () {
        setTimeout(function () {
          options.handler({
            razorpay_order_id: options.order_id,
            razorpay_payment_id: "pay_e2e_1",
            razorpay_signature: "e2e-fake-signature",
          });
        }, 50);
      },
    };
  };
`;
