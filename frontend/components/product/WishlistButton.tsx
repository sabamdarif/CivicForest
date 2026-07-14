"use client";

import { HeartIcon } from "@/components/ui/icons";
import { useWishlist } from "@/lib/wishlist/WishlistProvider";

/**
 * Heart toggle backed by the server wishlist. Two visual variants: the floating badge
 * on product cards, and the bordered square next to add-to-cart on the product page.
 */
export function WishlistButton({
  productId,
  variant = "badge",
  className = "",
}: {
  productId: string;
  variant?: "badge" | "square";
  className?: string;
}) {
  const { has, toggle } = useWishlist();
  const active = has(productId);

  const base =
    variant === "badge"
      ? "flex h-8 w-8 items-center justify-center rounded-full bg-cream/90 shadow-sm transition hover:text-gold"
      : "flex h-11 w-11 items-center justify-center rounded-sm border border-black/15 transition hover:text-gold";

  return (
    <button
      type="button"
      aria-label={active ? "Remove from wishlist" : "Add to wishlist"}
      aria-pressed={active}
      onClick={(e) => {
        e.preventDefault();
        void toggle(productId);
      }}
      className={`${base} ${active ? "text-gold" : "text-ink"} ${className}`}
    >
      <HeartIcon className={variant === "badge" ? "h-4 w-4" : "h-5 w-5"} filled={active} />
    </button>
  );
}
