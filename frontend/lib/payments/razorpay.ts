"use client";

// Loads Razorpay's hosted-checkout script once and opens it. Keys and amounts come
// straight from the server's /checkout response — the browser never computes a price
// or knows the secret (plan.md §9). Fulfilment is the server-to-server webhook; the
// handler callback here is advisory UI feedback only.

const SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

interface RazorpayHandlerResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface RazorpayOptions {
  key: string;
  amount: number; // paise
  currency: string;
  name: string;
  description?: string;
  order_id: string;
  prefill?: { name?: string; email?: string; contact?: string };
  theme?: { color?: string };
  handler: (response: RazorpayHandlerResponse) => void;
  modal?: { ondismiss?: () => void };
}

interface RazorpayInstance {
  open: () => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}

let loading: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.Razorpay) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.onload = () => resolve();
    script.onerror = () => {
      loading = null;
      reject(new Error("Failed to load Razorpay checkout."));
    };
    document.body.appendChild(script);
  });
  return loading;
}

export async function openRazorpayCheckout(options: RazorpayOptions): Promise<void> {
  await loadScript();
  if (!window.Razorpay) throw new Error("Razorpay unavailable.");
  new window.Razorpay(options).open();
}
