/* The Razorpay handoff (task 4). Payment is the one documented JavaScript exception: the rest
 * of checkout is a form that posts and re-renders. This opens the hosted checkout modal for the
 * gateway order the server already created, posts the callback to /payments/verify for fast UI
 * feedback, then sends the customer to the thank-you page. The webhook, not this callback, is
 * what actually marks the order paid, so a closed tab or a missed callback still gets fulfilled.
 */

const root = document.querySelector("[data-checkout-pay]");

if (root && window.Razorpay) {
  const orderNumber = root.dataset.orderNumber;
  const csrf = root.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";
  const live = root.querySelector("[data-pay-live]");
  const thankYou = `/checkout/thank-you/${encodeURIComponent(orderNumber)}/`;

  const say = (message, error = false) => {
    live.innerHTML = `<p class="${error ? "field__error" : "checkout-pay__note"}">${message}</p>`;
  };

  const verify = async (response) => {
    // Advisory: tells the thank-you page the callback arrived. The webhook is authoritative,
    // so a non-ok verify still lands the customer on the thank-you page to await confirmation.
    try {
      await fetch("/api/v1/payments/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
        }),
      });
    } catch {
      /* ignore: fulfilment does not depend on this call */
    }
    window.location.assign(thankYou);
  };

  const rzp = new Razorpay({
    key: root.dataset.key,
    amount: root.dataset.amount,
    currency: "INR",
    name: "CivicForest",
    description: `Order ${orderNumber}`,
    order_id: root.dataset.orderId,
    prefill: {
      name: root.dataset.name,
      email: root.dataset.email,
      contact: root.dataset.contact,
    },
    theme: { color: "#c9a227" },
    handler: verify,
  });

  rzp.on("payment.failed", (response) => {
    say(
      `Payment failed: ${response.error?.description || "please try again"}. ` +
        `You can retry from your order in the account area.`,
      true,
    );
  });

  const open = (event) => {
    event?.preventDefault();
    rzp.open();
  };

  root.querySelector("[data-pay-now]")?.addEventListener("click", open);
  // Open on load too, so a returning customer does not have to hunt for the button.
  rzp.open();
}
