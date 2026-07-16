"use client";

import { useMemo, useState } from "react";

import { CustomDesignUpload } from "@/components/product/CustomDesignUpload";
import { WishlistButton } from "@/components/product/WishlistButton";
import { ArrowRight } from "@/components/ui/icons";
import { ApiError } from "@/lib/api/client";
import type { ProductDetail } from "@/lib/api/types";
import { formatPrice } from "@/lib/brand/format";
import { useCart } from "@/lib/cart/CartProvider";

/**
 * Size/color selection + add-to-cart. Selection and quantity are client UI state;
 * the actual price a customer pays is always recomputed server-side at checkout
 * (plan.md §10) — this panel only displays it.
 */
export function ProductPurchasePanel({ product }: { product: ProductDetail }) {
  const colors = product.colors;
  const [color, setColor] = useState(colors[0]?.name ?? "");
  const [size, setSize] = useState("");
  const [qty, setQty] = useState(1);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { addItem } = useCart();

  // Sizes available for the chosen color, based on in-stock variants.
  const sizesForColor = useMemo(() => {
    const set = new Map<string, boolean>();
    for (const v of product.variants) {
      if (v.color === color) set.set(v.size, v.in_stock);
    }
    return set;
  }, [product.variants, color]);

  const selectedVariant = product.variants.find(
    (v) => v.color === color && v.size === size,
  );
  const displayPrice = selectedVariant?.price ?? product.price_from;
  const canAdd = Boolean(selectedVariant?.in_stock);

  async function onAddToCart() {
    if (!selectedVariant) return;
    setError(null);
    setAdding(true);
    try {
      await addItem(selectedVariant.id, qty);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add to cart.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow">{product.category}</p>
        <h1 className="mt-2 font-serif text-3xl text-ink sm:text-4xl">{product.name}</h1>
        <p className="mt-3 text-2xl font-semibold text-ink">{formatPrice(displayPrice)}</p>
        <p className="mt-1 text-xs text-ink/50">Inclusive of all taxes</p>
      </div>

      {colors.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium text-ink">
            Color: <span className="text-ink/60">{color}</span>
          </p>
          <div className="flex flex-wrap gap-2.5">
            {colors.map((c) => (
              <button
                key={c.name}
                type="button"
                title={c.name}
                aria-label={c.name}
                onClick={() => {
                  setColor(c.name);
                  setSize("");
                }}
                className={`h-8 w-8 rounded-full border-2 transition ${
                  color === c.name ? "border-gold" : "border-black/10"
                }`}
                style={{ backgroundColor: c.hex || "#ccc" }}
              />
            ))}
          </div>
        </div>
      )}

      {product.sizes.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Size</p>
          <div className="flex flex-wrap gap-2">
            {product.sizes.map((s) => {
              const inStock = sizesForColor.get(s);
              const available = sizesForColor.has(s) && inStock;
              return (
                <button
                  key={s}
                  type="button"
                  disabled={!available}
                  onClick={() => setSize(s)}
                  className={`h-10 min-w-10 rounded-sm border px-3 text-sm transition ${
                    size === s
                      ? "border-charcoal bg-charcoal text-cream"
                      : available
                        ? "border-black/15 text-ink hover:border-charcoal"
                        : "cursor-not-allowed border-black/10 text-ink/25 line-through"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center gap-4">
        <div className="flex items-center rounded-sm border border-black/15">
          <button
            type="button"
            aria-label="Decrease quantity"
            onClick={() => setQty((q) => Math.max(1, q - 1))}
            className="px-3 py-2.5 text-ink/70 hover:text-ink"
          >
            −
          </button>
          <span className="w-8 text-center text-sm">{qty}</span>
          <button
            type="button"
            aria-label="Increase quantity"
            onClick={() => setQty((q) => q + 1)}
            className="px-3 py-2.5 text-ink/70 hover:text-ink"
          >
            +
          </button>
        </div>

        <button
          type="button"
          disabled={!canAdd || adding}
          onClick={onAddToCart}
          className="btn-dark flex-1 justify-center disabled:opacity-40"
        >
          {adding
            ? "Adding…"
            : canAdd
              ? "Add to Cart"
              : size
                ? "Out of Stock"
                : "Select a Size"}
          {canAdd && !adding && <ArrowRight />}
        </button>

        <WishlistButton productId={product.id} variant="square" />
      </div>

      {error && (
        <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      <CustomDesignUpload
        variantId={selectedVariant?.id ?? null}
        selectionHint={!selectedVariant ? "Select a color and size first." : null}
      />

      {product.description && (
        <div className="border-t border-black/10 pt-5 text-sm leading-relaxed text-ink/70">
          {product.description}
        </div>
      )}

      <dl className="grid grid-cols-2 gap-3 border-t border-black/10 pt-5 text-sm">
        {product.material && (
          <>
            <dt className="text-ink/50">Material</dt>
            <dd className="text-ink">{product.material}</dd>
          </>
        )}
        <dt className="text-ink/50">Category</dt>
        <dd className="text-ink">{product.category}</dd>
      </dl>
    </div>
  );
}
