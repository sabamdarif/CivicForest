// Account profile + saved addresses. Used to prefill the checkout form. All queries are
// scoped to the authenticated user server-side (plan.md §5).

import { apiFetch } from "./client";
import type { Address, CurrentUser, Paginated, ShippingAddressInput } from "./types";

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/account/me", { revalidate: 0 });
}

export type ProfileInput = Partial<
  Pick<CurrentUser, "first_name" | "last_name" | "phone" | "marketing_opt_in">
>;

export async function updateCurrentUser(patch: ProfileInput): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/account/me", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export type AddressInput = ShippingAddressInput & { is_default?: boolean };

export async function createAddress(input: AddressInput): Promise<Address> {
  return apiFetch<Address>("/account/addresses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** May reject with ApiError code "reauthentication_required" — reauthenticate and retry. */
export async function updateAddress(id: string, input: AddressInput): Promise<Address> {
  return apiFetch<Address>(`/account/addresses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

/** May reject with ApiError code "reauthentication_required" — reauthenticate and retry. */
export async function deleteAddress(id: string): Promise<void> {
  await apiFetch<void>(`/account/addresses/${id}`, { method: "DELETE" });
}

export async function getAddresses(): Promise<Address[]> {
  const data = await apiFetch<Paginated<Address> | Address[]>("/account/addresses", {
    revalidate: 0,
  });
  // The viewset paginates; tolerate either shape.
  return Array.isArray(data) ? data : data.results;
}
