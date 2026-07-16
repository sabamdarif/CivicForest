"use client";

// Slide-over cart. Reads the shared server-priced cart from CartProvider; quantity
// steppers and remove are optimistic-by-refetch (each mutation returns the re-priced
// cart). Totals shown here are always the server's numbers, never computed here.

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { useCart } from "@/lib/cart/CartProvider";
import { formatPrice } from "@/lib/brand/format";

export function CartDrawer() {
  const { cart, drawerOpen, closeDrawer, setQuantity, removeItem } = useCart();
  const [busy, setBusy] = useState<string | null>(null);

  async function change(variantId: string, quantity: number) {
    setBusy(variantId);
    try {
      await setQuantity(variantId, quantity);
    } catch {
      /* server message already user-safe; leave state as-is */
    } finally {
      setBusy(null);
    }
  }

  const lines = cart?.lines ?? [];

  return (
    <>
      <div
        aria-hidden={!drawerOpen}
        onClick={closeDrawer}
        className={`fixed inset-0 z-50 bg-charcoal/40 transition-opacity ${
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        role="dialog"
        aria-label="Shopping cart"
        aria-modal="true"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-cream shadow-card transition-transform ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="flex items-center justify-between border-b border-black/10 px-6 py-5">
          <h2 className="font-serif text-xl text-ink">Your Cart</h2>
          <button
            type="button"
            onClick={closeDrawer}
            aria-label="Close cart"
            className="text-ink/60 hover:text-ink"
          >
            ✕
          </button>
        </header>

        {lines.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
            <p className="text-ink/60">Your cart is empty.</p>
            <Link href="/shop" onClick={closeDrawer} className="btn-dark">
              Continue Shopping
            </Link>
          </div>
        ) : (
          <>
            <ul className="flex-1 divide-y divide-black/10 overflow-y-auto px-6 scroll-thin">
              {lines.map((line) => (
                <li key={line.variant_id} className="flex gap-4 py-4">
                  <div className="relative h-24 w-20 shrink-0 overflow-hidden rounded-sm bg-cream-dark">
                    {line.thumbnail && (
                      <Image
                        src={line.thumbnail}
                        alt={line.product_name}
                        fill
                        sizes="80px"
                        className="object-cover"
                      />
                    )}
                  </div>
                  <div className="flex flex-1 flex-col">
                    <Link
                      href={`/product/${line.product_slug}`}
                      onClick={closeDrawer}
                      className="text-sm font-medium text-ink hover:text-gold"
                    >
                      {line.product_name}
                    </Link>
                    <p className="mt-0.5 text-xs text-ink/50">
                      {line.color} · {line.size}
                    </p>
                    <div className="mt-auto flex items-center justify-between">
                      <div className="flex items-center rounded-sm border border-black/15">
                        <button
                          type="button"
                          aria-label="Decrease quantity"
                          disabled={busy === line.variant_id}
                          onClick={() => change(line.variant_id, line.quantity - 1)}
                          className="px-2.5 py-1 text-ink/70 hover:text-ink disabled:opacity-40"
                        >
                          −
                        </button>
                        <span className="w-8 text-center text-sm">{line.quantity}</span>
                        <button
                          type="button"
                          aria-label="Increase quantity"
                          disabled={
                            busy === line.variant_id ||
                            line.quantity >= line.available_stock
                          }
                          onClick={() => change(line.variant_id, line.quantity + 1)}
                          className="px-2.5 py-1 text-ink/70 hover:text-ink disabled:opacity-40"
                        >
                          +
                        </button>
                      </div>
                      <span className="text-sm font-semibold text-ink">
                        {formatPrice(line.line_total)}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${line.product_name}`}
                    onClick={() => removeItem(line.variant_id)}
                    className="self-start text-xs text-ink/40 hover:text-red-600"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>

            <footer className="border-t border-black/10 px-6 py-5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-ink/60">Subtotal</span>
                <span className="font-medium text-ink">
                  {formatPrice(cart?.subtotal ?? "0")}
                </span>
              </div>
              {cart && Number(cart.discount) > 0 && (
                <div className="mt-1 flex items-center justify-between text-sm text-gold">
                  <span>Discount</span>
                  <span>−{formatPrice(cart.discount)}</span>
                </div>
              )}
              <p className="mt-1 text-xs text-ink/50">
                Shipping & total calculated at checkout.
              </p>
              <Link
                href="/cart"
                onClick={closeDrawer}
                className="btn-dark mt-4 w-full justify-center"
              >
                View Cart & Checkout <ArrowRight />
              </Link>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
