"use client";

// Single order detail. Every value is a server snapshot (read-only). When the order has
// custom-print items, we also surface the caller's Qikink tracking (AWB/status) — the
// read API scopes custom designs to the user, so we show those carrying tracking.

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { getCustomDesigns } from "@/lib/api/customDesigns";
import { getOrder } from "@/lib/api/orders";
import type { CustomDesignOrder, Order } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams<{ order_number: string }>();
  const orderNumber = params.order_number;

  const [order, setOrder] = useState<Order | null>(null);
  const [designs, setDesigns] = useState<CustomDesignOrder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOrder(orderNumber)
      .then(async (o) => {
        setOrder(o);
        if (o.has_custom_items) {
          setDesigns(await getCustomDesigns().catch(() => []));
        }
      })
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/login");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("Order not found.");
        } else {
          setError("Couldn't load this order.");
        }
      });
  }, [orderNumber, router]);

  if (error) {
    return (
      <div className="container-page py-24 text-center">
        <p className="text-ink/60">{error}</p>
        <Link href="/account/orders" className="mt-6 inline-block text-sm text-gold hover:underline">
          Back to orders
        </Link>
      </div>
    );
  }

  if (!order) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  const tracked = designs.filter((d) => d.tracking_awb || d.qikink_status);

  return (
    <div className="container-page py-16">
      <Link href="/account/orders" className="text-sm text-gold hover:underline">
        ← Orders
      </Link>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Order</p>
          <h1 className="mt-1 font-serif text-3xl text-ink">#{order.order_number}</h1>
          <p className="mt-1 text-sm text-ink/50">
            {new Date(order.created_at).toLocaleString("en-IN")}
          </p>
        </div>
        <span className="rounded-full bg-charcoal/5 px-4 py-1.5 text-sm font-semibold uppercase tracking-wide text-ink/70">
          {order.status_display}
        </span>
      </div>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_20rem]">
        <div>
          <h2 className="font-serif text-lg text-ink">Items</h2>
          <ul className="mt-3 divide-y divide-black/10 rounded-sm border border-black/10">
            {order.items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-4 p-4">
                <div>
                  <p className="text-sm font-medium text-ink">
                    {item.product_name}
                    {item.is_custom && (
                      <span className="ml-2 rounded-sm bg-gold/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gold-dark">
                        Custom
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-ink/50">
                    {[item.size, item.color].filter(Boolean).join(" · ")} · Qty {item.quantity}
                  </p>
                </div>
                <p className="text-sm font-semibold text-ink">{formatPrice(item.line_total)}</p>
              </li>
            ))}
          </ul>

          {tracked.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-lg text-ink">Custom print tracking</h2>
              <ul className="mt-3 space-y-3">
                {tracked.map((d) => (
                  <li key={d.id} className="rounded-sm border border-black/10 p-4 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink capitalize">
                        {d.qikink_status || d.submit_status.replace(/_/g, " ")}
                      </span>
                      {d.tracking_awb && (
                        <span className="text-ink/60">AWB: {d.tracking_awb}</span>
                      )}
                    </div>
                    {d.tracking_link && (
                      <a
                        href={d.tracking_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-block text-gold hover:underline"
                      >
                        Track shipment →
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <div className="rounded-sm border border-black/10 p-5 text-sm">
            <h2 className="font-serif text-base text-ink">Summary</h2>
            <dl className="mt-3 space-y-2 text-ink/70">
              <Row label="Subtotal" value={formatPrice(order.subtotal)} />
              {Number.parseFloat(order.discount) > 0 && (
                <Row label={`Discount${order.coupon_code ? ` (${order.coupon_code})` : ""}`} value={`− ${formatPrice(order.discount)}`} />
              )}
              <Row
                label="Shipping"
                value={Number.parseFloat(order.shipping_fee) === 0 ? "Free" : formatPrice(order.shipping_fee)}
              />
              <div className="flex justify-between border-t border-black/10 pt-2 font-semibold text-ink">
                <span>Total</span>
                <span>{formatPrice(order.total)}</span>
              </div>
            </dl>
          </div>

          <div className="rounded-sm border border-black/10 p-5 text-sm">
            <h2 className="font-serif text-base text-ink">Shipping to</h2>
            <address className="mt-3 not-italic leading-relaxed text-ink/70">
              {order.ship_full_name}
              <br />
              {order.ship_line1}
              {order.ship_line2 && (
                <>
                  <br />
                  {order.ship_line2}
                </>
              )}
              <br />
              {order.ship_city}, {order.ship_state} {order.ship_postal_code}
              <br />
              {order.ship_country}
              <br />
              {order.phone}
            </address>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
