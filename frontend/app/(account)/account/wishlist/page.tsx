"use client";

// Saved items. Loads the full wishlist entries (product name/price/thumb) so it can
// render cards, and lets the shared WishlistProvider drive the heart toggle. A 401 here
// just means signed out → send to login.

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { WishlistButton } from "@/components/product/WishlistButton";
import { ApiError } from "@/lib/api/client";
import { getWishlist } from "@/lib/api/wishlist";
import type { WishlistEntry } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";
import { useWishlist } from "@/lib/wishlist/WishlistProvider";

export default function WishlistPage() {
  const router = useRouter();
  const { ids } = useWishlist();
  const [entries, setEntries] = useState<WishlistEntry[] | null>(null);

  useEffect(() => {
    getWishlist()
      .then(setEntries)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/login");
        } else {
          setEntries([]);
        }
      });
  }, [router]);

  if (entries === null) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  // Reflect removals done via the heart without refetching: hide entries dropped from ids.
  const visible = entries.filter((e) => ids.has(e.product_id));

  return (
    <div className="container-page py-16">
      <p className="eyebrow">My Account</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">Wishlist</h1>

      {visible.length === 0 ? (
        <div className="mt-10 rounded-sm border border-black/10 p-12 text-center">
          <p className="text-ink/60">Nothing saved yet.</p>
          <Link href="/shop" className="btn-dark mt-6">
            Browse the shop
          </Link>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-2 gap-x-5 gap-y-8 md:grid-cols-4">
          {visible.map((e) => (
            <article key={e.id} className="group">
              <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-cream-dark">
                <Link href={`/product/${e.slug}`} aria-label={e.name}>
                  {e.thumbnail ? (
                    <Image
                      src={e.thumbnail}
                      alt={e.name}
                      fill
                      sizes="(max-width: 768px) 50vw, 25vw"
                      className="object-cover transition duration-500 group-hover:scale-[1.03]"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-charcoal/20">
                      <span className="font-serif text-4xl tracking-brand">cF</span>
                    </div>
                  )}
                </Link>
                <WishlistButton productId={e.product_id} variant="badge" className="absolute right-3 top-3" />
              </div>
              <div className="mt-3 space-y-1">
                <Link href={`/product/${e.slug}`} className="block text-sm font-medium text-ink hover:text-gold">
                  {e.name}
                </Link>
                <p className="text-sm font-semibold text-ink">{formatPrice(e.price_from)}</p>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
