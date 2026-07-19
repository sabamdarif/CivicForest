// The critical money path: search → product → cart → checkout → paid.
// Razorpay is stubbed at two seams only — the hosted-checkout script (browser) and
// the outbound order-create call (RAZORPAY_FAKE_MODE) — everything else, including
// the HMAC-verified webhook and stock-locking fulfilment, is the real code path.
import crypto from "node:crypto";

import { expect, test } from "@playwright/test";

import { API, FAKE_RAZORPAY_JS, WEBHOOK_SECRET, signup, uniqueEmail } from "./helpers";

test("search → add to cart → checkout → webhook marks order paid", async ({ page, request }) => {
  await signup(page, uniqueEmail("buyer"));

  // Search via the header overlay; suggestions come from the API fallback.
  await page.goto("/");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByLabel("Search products").fill("Classic Black");
  await page.getByRole("button", { name: /Classic Black Tee/ }).first().click();
  await page.waitForURL("**/product/classic-black-tee");

  // Pick a size (first colour is preselected) and add to the cart.
  await page.getByRole("button", { name: "M", exact: true }).click();
  await page.getByRole("button", { name: /Add to Cart/i }).click();
  await expect(page.getByLabel(/Cart \(1 items?\)/)).toBeVisible();

  await page.goto("/cart");
  await page.getByRole("link", { name: /Proceed to Checkout/i }).click();
  await page.waitForURL("**/checkout");

  // Stub Razorpay's hosted checkout before paying.
  await page.route("https://checkout.razorpay.com/**", (route) =>
    route.fulfill({ contentType: "application/javascript", body: FAKE_RAZORPAY_JS }),
  );

  await page.getByLabel("Full name").fill("E2E Buyer");
  await page.getByLabel("Phone").fill("9999999999");
  await page.getByLabel("Address line 1").fill("1 MG Road");
  await page.getByLabel("City").fill("Bengaluru");
  await page.getByLabel("State").fill("Karnataka");
  await page.getByLabel("Postal code").fill("560001");

  const checkoutResponse = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/checkout") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: /^Pay/ }).click();
  const session = await (await checkoutResponse).json();
  expect(session.razorpay_order_id).toBeTruthy();

  // Fire the authoritative webhook, HMAC-signed exactly like Razorpay would.
  const body = JSON.stringify({
    id: `evt_e2e_${Date.now()}`,
    event: "payment.captured",
    payload: {
      payment: { entity: { order_id: session.razorpay_order_id, id: "pay_e2e_1" } },
    },
  });
  const signature = crypto.createHmac("sha256", WEBHOOK_SECRET).update(body).digest("hex");
  const webhook = await request.post(`${API}/api/v1/payments/webhook/razorpay`, {
    data: body,
    headers: { "Content-Type": "application/json", "X-Razorpay-Signature": signature },
  });
  expect(webhook.ok()).toBeTruthy();
  expect((await webhook.json()).status).toBe("fulfilled");

  // The page polls order status and flips to the confirmation screen.
  await expect(page.getByRole("heading", { name: "Order confirmed" })).toBeVisible({
    timeout: 45_000,
  });
  await expect(page.getByText(session.order_number)).toBeVisible();

  // The paid order shows up in account history.
  await page.goto("/account/orders");
  await expect(page.getByText(session.order_number)).toBeVisible();
});
