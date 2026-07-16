"use client";

// The signed-in user's order history. Orders are read-only server snapshots; custom-print
// items carry Qikink tracking that appears on the detail page. A 401 bounces to login.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { ApiError } from "@/lib/api/client";
import { getOrders } from "@/lib/api/orders";
import type { Order } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";

export default function OrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOrders()
      .then(setOrders)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/login");
        } else {
          setError("Couldn't load your orders.");
        }
      });
  }, [router]);

  if (error) {
    return <div className="container-page py-24 text-center text-ink/60">{error}</div>;
  }

  if (!orders) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  return (
    <div className="container-page py-16">
      <p className="eyebrow">My Account</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">Orders</h1>

      {orders.length === 0 ? (
        <div className="mt-10 rounded-sm border border-black/10 bg-cream p-10 text-center">
          <p className="text-ink/60">You haven&apos;t placed any orders yet.</p>
          <Link href="/shop" className="btn-dark mt-6">
            Start shopping <ArrowRight />
          </Link>
        </div>
      ) : (
        <ul className="mt-10 space-y-4">
          {orders.map((order) => (
            <li key={order.order_number}>
              <Link
                href={`/account/orders/${order.order_number}`}
                className="flex items-center justify-between gap-4 rounded-sm border border-black/10 bg-cream p-5 transition hover:border-charcoal"
              >
                <div>
                  <p className="font-medium text-ink">#{order.order_number}</p>
                  <p className="mt-1 text-sm text-ink/50">
                    {new Date(order.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}{" "}
                    · {order.items.length} item{order.items.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="text-right">
                  <span className="inline-block rounded-full bg-charcoal/5 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink/70">
                    {order.status_display}
                  </span>
                  <p className="mt-1 font-semibold text-ink">{formatPrice(order.total)}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
