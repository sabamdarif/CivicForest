// Wishlist data access. Requires an authenticated session; a 401 from the server is
// surfaced as an ApiError so callers can prompt for login.

import { apiFetch } from "./client";
import type { WishlistEntry } from "./types";

export async function getWishlist(): Promise<WishlistEntry[]> {
  const data = await apiFetch<{ results: WishlistEntry[]; count: number }>(
    "/wishlist",
    { revalidate: 0 },
  );
  return data.results;
}

/** Toggle a product in/out of the wishlist. Returns whether it is now wishlisted. */
export async function toggleWishlist(productId: string): Promise<boolean> {
  const data = await apiFetch<{ product_id: string; wishlisted: boolean }>(
    "/wishlist",
    { method: "POST", body: JSON.stringify({ product_id: productId }) },
  );
  return data.wishlisted;
}

export async function removeWishlist(productId: string): Promise<void> {
  await apiFetch<void>(`/wishlist/${productId}`, { method: "DELETE" });
}
