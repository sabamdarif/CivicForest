// The full money path: log in, add a seeded variant, complete checkout to the Razorpay pay page,
// then simulate capture by POSTing a signed webhook (the sanctioned e2e approach, no modal).
// Fulfilment runs on the webhook, so the order should read Paid in the account area afterwards.

const crypto = require("crypto");
const { test, expect } = require("@playwright/test");
const { login, addSeededVariantToCart } = require("./helpers");

const WEBHOOK_SECRET = "e2e-webhook-secret";

test("checkout plus a signed webhook marks the order paid", async ({ page, request }) => {
  await login(page);
  await addSeededVariantToCart(page);

  await page.goto("/checkout/");
  await page.fill('input[name="phone"]', "9999999999");
  await page.fill('input[name="full_name"]', "Test Buyer");
  await page.fill('input[name="line1"]', "1 Test Street");
  await page.fill('input[name="postal_code"]', "560001");
  await page.fill('input[name="city"]', "Bengaluru");
  await page.fill('input[name="state"]', "Karnataka");
  await page.check('input[name="accept_terms"]');
  await Promise.all([
    page.waitForURL("**/checkout/pay/**"),
    page.getByRole("button", { name: /^Pay / }).click(),
  ]);

  const payEl = page.locator("[data-checkout-pay]");
  const orderId = await payEl.getAttribute("data-order-id");
  const amount = await payEl.getAttribute("data-amount");
  const orderNumber = await payEl.getAttribute("data-order-number");
  expect(orderId).toMatch(/^order_fake_/);
  expect(Number(amount)).toBeGreaterThan(0);

  const body = JSON.stringify({
    id: `evt_e2e_${Date.now()}`,
    event: "payment.captured",
    payload: {
      payment: {
        entity: {
          id: "pay_e2e",
          order_id: orderId,
          amount: parseInt(amount, 10),
          currency: "INR",
        },
      },
    },
  });
  const signature = crypto.createHmac("sha256", WEBHOOK_SECRET).update(body).digest("hex");
  const resp = await request.post("/api/v1/payments/webhook/razorpay", {
    headers: { "Content-Type": "application/json", "X-Razorpay-Signature": signature },
    data: body,
  });
  expect(resp.status()).toBe(200);

  await page.goto("/account/orders/");
  const orderCard = page.locator(".card").filter({ hasText: orderNumber });
  await expect(orderCard).toContainText("Paid");
});
