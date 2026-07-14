import Image from "next/image";
import Link from "next/link";

import { WishlistButton } from "@/components/product/WishlistButton";
import type { ProductListItem } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";

/** Product card used across Just Landed, the shop grid, and search results. */
export function ProductCard({ product }: { product: ProductListItem }) {
  return (
    <article className="group animate-fade-in">
      <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-cream-dark">
        <Link href={`/product/${product.slug}`} aria-label={product.name}>
          {product.thumbnail ? (
            <Image
              src={product.thumbnail}
              alt={product.name}
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

        {product.is_new && (
          <span className="absolute left-3 top-3 rounded-sm bg-charcoal px-2 py-1 text-[10px] font-semibold uppercase tracking-brand text-gold">
            New
          </span>
        )}

        <WishlistButton
          productId={product.id}
          variant="badge"
          className="absolute right-3 top-3"
        />
      </div>

      <div className="mt-3 space-y-1">
        <Link
          href={`/product/${product.slug}`}
          className="block text-sm font-medium text-ink transition hover:text-gold"
        >
          {product.name}
        </Link>
        <p className="text-sm font-semibold text-ink">
          {formatPrice(product.price_from)}
        </p>
        {product.colors.length > 0 && (
          <div className="flex items-center gap-1.5 pt-1">
            {product.colors.slice(0, 5).map((c) => (
              <span
                key={c.name}
                title={c.name}
                className="h-3.5 w-3.5 rounded-full border border-black/10"
                style={{ backgroundColor: c.hex || "#ccc" }}
              />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
