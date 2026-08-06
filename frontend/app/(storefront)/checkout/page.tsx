"use client";

// Checkout: collect/prefill a shipping address, create the order + Razorpay order
// server-side, open hosted checkout, then poll the order status (the webhook fulfils
// it out-of-band, so the UI waits for the server to flip it to paid). No money math
// or price input ever happens here (plan.md §9/§10).

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getAddresses } from "@/lib/api/account";
import { ApiError } from "@/lib/api/client";
import { checkout, getOrder, verifyPayment } from "@/lib/api/orders";
import type { Address, ShippingAddressInput } from "@/lib/api/types";
import { getSession } from "@/lib/auth/allauth";
import { useCart } from "@/lib/cart/CartProvider";
import { formatPrice } from "@/lib/brand/format";
import { openRazorpayCheckout } from "@/lib/payments/razorpay";

const EMPTY: ShippingAddressInput = {
  full_name: "",
  phone: "",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "IN",
};

type Phase = "form" | "paying" | "confirming" | "done";

export default function CheckoutPage() {
  const router = useRouter();
  const { cart, loading: cartLoading, refresh } = useCart();
  const [form, setForm] = useState<ShippingAddressInput>(EMPTY);
  const [saveAddress, setSaveAddress] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");
  const [error, setError] = useState<string | null>(null);
  const [orderNumber, setOrderNumber] = useState<string | null>(null);
  const checkoutKey = useRef<string | null>(null);
  const cartSignature = cart?.lines
    .map((line) => `${line.variant_id}:${line.quantity}`)
    .sort()
    .join("|");

  useEffect(() => {
    checkoutKey.current = null;
  }, [cartSignature]);

  // Gate on auth (checkout requires it), then prefill from a saved address.
  useEffect(() => {
    getSession()
      .then((s) => {
        if (!s.meta?.is_authenticated) {
          router.replace("/login?next=/checkout");
          return;
        }
        return getAddresses();
      })
      .then((addresses?: Address[]) => {
        const a = addresses?.[0];
        if (a) {
          setForm({
            full_name: a.full_name,
            phone: a.phone,
            line1: a.line1,
            line2: a.line2,
            city: a.city,
            state: a.state,
            postal_code: a.postal_code,
            country: a.country || "IN",
          });
        }
      })
      .catch(() => {});
  }, [router]);

  function set<K extends keyof ShippingAddressInput>(key: K, value: ShippingAddressInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  // Poll the order until the webhook flips it to a paid/processing state (or give up).
  async function pollUntilPaid(order: string): Promise<boolean> {
    for (let i = 0; i < 20; i++) {
      try {
        const o = await getOrder(order);
        if (["paid", "processing", "shipped", "delivered"].includes(o.status)) return true;
      } catch {
        /* transient — keep polling */
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
    return false;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPhase("paying");
    try {
      checkoutKey.current ??= crypto.randomUUID();
      const session = await checkout(form, saveAddress, checkoutKey.current);
      setOrderNumber(session.order_number);

      await openRazorpayCheckout({
        key: session.razorpay_key_id,
        amount: session.amount_paise,
        currency: session.currency,
        name: "CivicForest",
        description: `Order ${session.order_number}`,
        order_id: session.razorpay_order_id,
        prefill: { name: form.full_name, contact: form.phone },
        theme: { color: "#C89B4A" },
        modal: {
          ondismiss: () => {
            setPhase("form");
            setError("Payment cancelled. Your order is saved and can be retried.");
          },
        },
        handler: async (resp) => {
          setPhase("confirming");
          // Advisory verify for instant feedback; the webhook is authoritative.
          await verifyPayment({
            razorpay_order_id: resp.razorpay_order_id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
          }).catch(() => false);
          const paid = await pollUntilPaid(session.order_number);
          await refresh(); // cart is cleared server-side on fulfilment
          if (paid) {
            setPhase("done");
          } else {
            // Payment likely succeeded but confirmation is lagging — send them to the order.
            router.push(`/account/orders/${session.order_number}`);
          }
        },
      });
    } catch (err) {
      setPhase("form");
      setError(err instanceof ApiError ? err.message : "Checkout failed. Please try again.");
    }
  }

  if (cartLoading) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  if (phase === "done" && orderNumber) {
    return (
      <div className="container-page py-24 text-center">
        <p className="eyebrow">Thank you</p>
        <h1 className="mt-2 font-serif text-4xl text-ink">Order confirmed</h1>
        <p className="mt-3 text-ink/60">
          Your order <span className="font-semibold text-ink">{orderNumber}</span> is paid and
          being prepared.
        </p>
        <Link href={`/account/orders/${orderNumber}`} className="btn-dark mt-8">
          View order
        </Link>
      </div>
    );
  }

  if (!cart || cart.lines.length === 0) {
    return (
      <div className="container-page py-24 text-center">
        <h1 className="font-serif text-3xl text-ink">Your cart is empty</h1>
        <Link href="/shop" className="btn-dark mt-6">
          Continue shopping
        </Link>
      </div>
    );
  }

  const busy = phase !== "form";

  return (
    <div className="container-page py-12">
      <h1 className="font-serif text-3xl text-ink">Checkout</h1>

      <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_360px]">
        <form onSubmit={onSubmit} className="space-y-5">
          <h2 className="font-serif text-xl text-ink">Shipping address</h2>

          <Field label="Full name" value={form.full_name} onChange={(v) => set("full_name", v)} autoComplete="name" />
          <Field label="Phone" value={form.phone} onChange={(v) => set("phone", v)} autoComplete="tel" />
          <Field label="Address line 1" value={form.line1} onChange={(v) => set("line1", v)} autoComplete="address-line1" />
          <Field
            label="Address line 2 (optional)"
            value={form.line2 ?? ""}
            onChange={(v) => set("line2", v)}
            required={false}
            autoComplete="address-line2"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="City" value={form.city} onChange={(v) => set("city", v)} autoComplete="address-level2" />
            <Field label="State" value={form.state} onChange={(v) => set("state", v)} autoComplete="address-level1" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label="Postal code"
              value={form.postal_code}
              onChange={(v) => set("postal_code", v)}
              autoComplete="postal-code"
            />
            <Field label="Country" value={form.country ?? "IN"} onChange={(v) => set("country", v)} />
          </div>

          <label className="flex items-center gap-2 text-sm text-ink/70">
            <input
              type="checkbox"
              checked={saveAddress}
              onChange={(e) => setSaveAddress(e.target.checked)}
              className="h-4 w-4 accent-gold"
            />
            Save this address for next time
          </label>

          {error && (
            <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {error}
            </p>
          )}

          <button type="submit" disabled={busy} className="btn-dark w-full justify-center disabled:opacity-50">
            {phase === "paying"
              ? "Opening payment…"
              : phase === "confirming"
                ? "Confirming payment…"
                : `Pay ${formatPrice(cart.total)}`}
          </button>
        </form>

        <aside className="h-fit rounded-sm border border-black/10 bg-white p-6">
          <h2 className="font-serif text-lg text-ink">Order summary</h2>
          <ul className="mt-4 space-y-3 text-sm">
            {cart.lines.map((line) => (
              <li key={line.variant_id} className="flex justify-between gap-3">
                <span className="text-ink/70">
                  {line.product_name} · {line.size}/{line.color} × {line.quantity}
                </span>
                <span className="text-ink">{formatPrice(line.line_total)}</span>
              </li>
            ))}
          </ul>
          <dl className="mt-4 space-y-2 border-t border-black/10 pt-4 text-sm">
            <Row label="Subtotal" value={formatPrice(cart.subtotal)} />
            {Number.parseFloat(cart.discount) > 0 && (
              <Row label={`Discount${cart.coupon_code ? ` (${cart.coupon_code})` : ""}`} value={`− ${formatPrice(cart.discount)}`} />
            )}
            <Row label="Shipping" value={Number.parseFloat(cart.shipping) === 0 ? "Free" : formatPrice(cart.shipping)} />
            <div className="flex justify-between border-t border-black/10 pt-2 text-base font-semibold text-ink">
              <span>Total</span>
              <span>{formatPrice(cart.total)}</span>
            </div>
          </dl>
        </aside>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  required = true,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      <input
        type="text"
        required={required}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="input-field mt-1.5"
      />
    </label>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-ink/70">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
