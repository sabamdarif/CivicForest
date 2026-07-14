// Orders, checkout and payment verification. The checkout call snapshots the cart into
// an order and opens a Razorpay order server-side (amount computed there — the browser
// never sends a price). The verify call is advisory UI feedback only; the authoritative
// fulfilment path is the server-to-server webhook (plan.md §9).

import { apiFetch } from "./client";
import type {
  CheckoutResponse,
  Order,
  Paginated,
  ShippingAddressInput,
} from "./types";

export async function getOrders(): Promise<Order[]> {
  const data = await apiFetch<Paginated<Order>>("/orders", { revalidate: 0 });
  return data.results;
}

export async function getOrder(orderNumber: string): Promise<Order> {
  return apiFetch<Order>(`/orders/${orderNumber}`, { revalidate: 0 });
}

export async function checkout(
  shippingAddress: ShippingAddressInput,
  saveAddress = false,
): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>("/checkout", {
    method: "POST",
    body: JSON.stringify({
      shipping_address: shippingAddress,
      save_address: saveAddress,
    }),
  });
}

export interface RazorpayCallback {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export async function verifyPayment(
  callback: RazorpayCallback,
): Promise<boolean> {
  const data = await apiFetch<{ verified: boolean }>("/payments/verify", {
    method: "POST",
    body: JSON.stringify(callback),
  });
  return data.verified;
}
