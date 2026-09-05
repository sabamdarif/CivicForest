/* The cart drawer, and the only JavaScript the cart needs (task 7).
 *
 * The contract from P6: every cart action already works as a form that posts and re-renders.
 * This saves the reload, by sending the same form with an X-Partial header and swapping in the
 * drawer the server returns. No total is computed here and no rupee is formatted here, because
 * the response is already finished markup: the server stays the only thing that knows the price.
 *
 * The forms carry {{ csrf_input }}, so FormData brings the token with it and there is no CSRF
 * helper to write. Anything unexpected falls through to a normal submit or navigation.
 */

import { openDialog } from "./modal.js";

const PARTIAL = { "X-Partial": "cart" };

const drawer = document.getElementById("cart-drawer");
const link = document.querySelector(".cart-link");
const live = document.querySelector("[data-cart-live]");

let loaded = false;

const syncCount = (units) => {
  if (live) {
    live.textContent = units
      ? `${units} item${units === 1 ? "" : "s"} in your cart`
      : "Your cart is empty";
  }
  if (!link) return;
  link.setAttribute("aria-label", `Cart, ${units} item${units === 1 ? "" : "s"}`);

  let count = link.querySelector(".cart-link__count");
  if (!units) {
    count?.remove();
    return;
  }
  if (!count) {
    count = document.createElement("span");
    count.className = "cart-link__count";
    count.setAttribute("aria-hidden", "true");
    link.append(count);
  }
  count.textContent = units;
};

/* The swap replaces the dialog's contents, never the dialog itself, so an open drawer does not
   blink shut and the ::backdrop stays put. */
const swap = (html) => {
  const fresh = new DOMParser().parseFromString(html, "text/html").getElementById("cart-drawer");
  if (!fresh) throw new Error("no drawer in that response");
  drawer.innerHTML = fresh.innerHTML;
  loaded = true;
  syncCount(Number(drawer.querySelector("[data-cart-drawer]")?.dataset.count ?? 0));
};

const load = async (url, options) => {
  const response = await fetch(url, { headers: PARTIAL, ...options });
  if (!response.ok) throw new Error(response.status);
  swap(await response.text());
};

/* The control that was clicked is gone with the markup around it, so a keyboard user has to be
   put back on its replacement rather than dropped at the top of the dialog. */
const refocus = (variant, op) => {
  const form = drawer.querySelector(`input[name="variant"][value="${variant}"]`)?.form;
  const target =
    (op && form?.querySelector(`[name="op"][value="${op}"]:not([disabled])`)) ||
    form?.querySelector(".stepper__input") ||
    drawer.querySelector("[data-dialog-close]");
  target?.focus();
};

if (drawer) {
  // modal.js already opens the dialog from the header's data-dialog-open, so this only fills it.
  document.addEventListener("click", async (event) => {
    if (!event.target.closest('[data-dialog-open="cart-drawer"]') || loaded) return;
    try {
      await load("/cart/");
    } catch {
      window.location.assign("/cart/");
    }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.fallback) return;
    // The drawer's own forms, and the product page's buy panel, which opens the drawer on add.
    if (!form.closest("#cart-drawer") && !form.closest("[data-buy]")) return;

    event.preventDefault();
    const body = new FormData(form);
    // A submit button's name and value are not in FormData, and op is what the button carries.
    if (event.submitter?.name) body.append(event.submitter.name, event.submitter.value);

    try {
      await load(form.action, { method: "POST", body });
    } catch {
      form.dataset.fallback = "1";
      form.requestSubmit(event.submitter);
      return;
    }
    openDialog("cart-drawer");
    refocus(body.get("variant"), event.submitter?.value);
  });
}
