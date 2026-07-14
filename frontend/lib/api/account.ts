// Account profile + saved addresses. Used to prefill the checkout form. All queries are
// scoped to the authenticated user server-side (plan.md §5).

import { apiFetch } from "./client";
import type { Address, CurrentUser, Paginated } from "./types";

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/account/me", { revalidate: 0 });
}

export async function getAddresses(): Promise<Address[]> {
  const data = await apiFetch<Paginated<Address> | Address[]>("/account/addresses", {
    revalidate: 0,
  });
  // The viewset paginates; tolerate either shape.
  return Array.isArray(data) ? data : data.results;
}
