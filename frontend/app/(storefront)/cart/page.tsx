"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { ApiError } from "@/lib/api/client";
import type { CartLine } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";
import { useCart } from "@/lib/cart/CartProvider";

export default function CartPage() {
  const router = useRouter();
  const { cart, loading, setQuantity, removeItem, applyCoupon, removeCoupon } =
    useCart();
  const [code, setCode] = useState("");
  const [couponError, setCouponError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onApplyCoupon(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setCouponError(null);
    setBusy(true);
    try {
      await applyCoupon(code.trim());
      setCode("");
    } catch (err) {
      setCouponError(err instanceof ApiError ? err.message : "Couldn't apply that code.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="container-page py-24 text-center text-ink/50">Loading your cart…</div>;
  }

  if (!cart || cart.lines.length === 0) {
    return (
      <div className="container-page py-24 text-center">
        <p className="eyebrow">Your Cart</p>
        <h1 className="mt-2 font-serif text-4xl text-ink">Your cart is empty.</h1>
        <p className="mt-3 text-ink/60">Find something you love.</p>
        <Link href="/shop" className="btn-dark mt-8 inline-flex">
          Continue Shopping <ArrowRight />
        </Link>
      </div>
    );
  }

  return (
    <div className="container-page py-12">
      <h1 className="font-serif text-4xl text-ink">Shopping Cart</h1>

      <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_360px]">
        <ul className="divide-y divide-black/10 border-y border-black/10">
          {cart.lines.map((line) => (
            <CartRow
              key={line.variant_id}
              line={line}
              onQty={(q) => setQuantity(line.variant_id, q)}
              onRemove={() => removeItem(line.variant_id)}
            />
          ))}
        </ul>

        <aside className="h-fit rounded-sm border border-black/10 bg-cream p-6">
          <h2 className="font-serif text-xl text-ink">Order Summary</h2>

          <form onSubmit={onApplyCoupon} className="mt-5">
            {cart.coupon_code ? (
              <div className="flex items-center justify-between rounded-sm bg-charcoal/5 px-3 py-2 text-sm">
                <span className="font-medium text-ink">
                  Coupon <span className="text-gold">{cart.coupon_code}</span> applied
                </span>
                <button
                  type="button"
                  onClick={() => void removeCoupon()}
                  className="text-xs uppercase tracking-wide text-ink/50 hover:text-ink"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="Coupon code"
                  className="input-field"
                  aria-label="Coupon code"
                />
                <button type="submit" disabled={busy} className="btn-outline shrink-0 disabled:opacity-50">
                  Apply
                </button>
              </div>
            )}
            {couponError && (
              <p className="mt-2 text-sm text-red-700" role="alert">
                {couponError}
              </p>
            )}
          </form>

          <dl className="mt-6 space-y-3 text-sm">
            <Row label="Subtotal" value={formatPrice(cart.subtotal)} />
            {Number(cart.discount) > 0 && (
              <Row label="Discount" value={`− ${formatPrice(cart.discount)}`} accent />
            )}
            <Row
              label="Shipping"
              value={Number(cart.shipping) === 0 ? "Free" : formatPrice(cart.shipping)}
            />
            <div className="flex items-center justify-between border-t border-black/10 pt-3 text-base font-semibold text-ink">
              <dt>Total</dt>
              <dd>{formatPrice(cart.total)}</dd>
            </div>
          </dl>

          <button
            type="button"
            onClick={() => router.push("/checkout")}
            className="btn-dark mt-6 w-full justify-center"
          >
            Proceed to Checkout <ArrowRight />
          </button>
          <p className="mt-3 text-center text-xs text-ink/50">
            Taxes included. Shipping calculated at checkout.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-ink/60">{label}</dt>
      <dd className={accent ? "text-gold" : "text-ink"}>{value}</dd>
    </div>
  );
}

function CartRow({
  line,
  onQty,
  onRemove,
}: {
  line: CartLine;
  onQty: (q: number) => Promise<unknown>;
  onRemove: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);

  async function change(next: number) {
    setBusy(true);
    try {
      await onQty(next);
    } finally {
      setBusy(false);
    }
  }

  const atStockCap = line.quantity >= line.available_stock;

  return (
    <li className="flex gap-4 py-5">
      <Link
        href={`/product/${line.product_slug}`}
        className="relative h-24 w-20 shrink-0 overflow-hidden rounded-sm bg-cream-dark"
      >
        {line.thumbnail ? (
          <Image src={line.thumbnail} alt={line.product_name} fill sizes="80px" className="object-cover" />
        ) : (
          <span className="flex h-full items-center justify-center font-serif text-charcoal/20">cF</span>
        )}
      </Link>

      <div className="flex flex-1 flex-col">
        <div className="flex justify-between gap-3">
          <Link
            href={`/product/${line.product_slug}`}
            className="text-sm font-medium text-ink hover:text-gold"
          >
            {line.product_name}
          </Link>
          <p className="text-sm font-semibold text-ink">{formatPrice(line.line_total)}</p>
        </div>
        <p className="mt-1 text-xs text-ink/50">
          {line.color} · {line.size}
        </p>
        <p className="text-xs text-ink/50">{formatPrice(line.unit_price)} each</p>

        <div className="mt-auto flex items-center justify-between pt-3">
          <div className="flex items-center rounded-sm border border-black/15">
            <button
              type="button"
              aria-label="Decrease quantity"
              disabled={busy}
              onClick={() => change(line.quantity - 1)}
              className="px-3 py-1.5 text-ink/70 hover:text-ink disabled:opacity-40"
            >
              −
            </button>
            <span className="w-8 text-center text-sm">{line.quantity}</span>
            <button
              type="button"
              aria-label="Increase quantity"
              disabled={busy || atStockCap}
              onClick={() => change(line.quantity + 1)}
              className="px-3 py-1.5 text-ink/70 hover:text-ink disabled:opacity-40"
            >
              +
            </button>
          </div>
          <button
            type="button"
            onClick={() => void onRemove()}
            className="text-xs uppercase tracking-wide text-ink/50 hover:text-red-700"
          >
            Remove
          </button>
        </div>
        {atStockCap && (
          <p className="pt-1 text-xs text-ink/40">Only {line.available_stock} in stock</p>
        )}
      </div>
    </li>
  );
}
