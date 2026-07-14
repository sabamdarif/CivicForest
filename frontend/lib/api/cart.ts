// Cart & coupon data access. Every call returns the freshly re-priced cart from the
// server — totals, discount and shipping are never computed in the browser (plan.md
// §10). Guest carts work without a login (session-bound); the server merges them into
// the user's cart on sign-in.

import { apiFetch } from "./client";
import type { Cart } from "./types";

export async function getCart(): Promise<Cart> {
  return apiFetch<Cart>("/cart", { revalidate: 0 });
}

export async function addCartItem(variantId: string, quantity = 1): Promise<Cart> {
  return apiFetch<Cart>("/cart/items", {
    method: "POST",
    body: JSON.stringify({ variant_id: variantId, quantity }),
  });
}

/** Set an absolute quantity for a line; quantity 0 removes it. */
export async function setCartItemQuantity(
  variantId: string,
  quantity: number,
): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${variantId}`, {
    method: "PATCH",
    body: JSON.stringify({ quantity }),
  });
}

export async function removeCartItem(variantId: string): Promise<Cart> {
  return apiFetch<Cart>(`/cart/items/${variantId}`, { method: "DELETE" });
}

export async function applyCoupon(code: string): Promise<Cart> {
  return apiFetch<Cart>("/cart/coupon", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function removeCoupon(): Promise<Cart> {
  return apiFetch<Cart>("/cart/coupon", { method: "DELETE" });
}
