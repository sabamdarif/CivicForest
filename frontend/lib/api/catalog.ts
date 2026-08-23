// Catalog data access. Server components call these with ISR; the shop page passes
// through filter/sort/pagination params from the URL.

import { apiFetch, buildQuery } from "./client";
import type {
  Category,
  Paginated,
  ProductDetail,
  ProductListItem,
  SearchResponse,
} from "./types";

const CATALOG_REVALIDATE = 120; // seconds

export async function getCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/catalog/categories", {
    revalidate: CATALOG_REVALIDATE,
  });
}

export interface ProductQuery {
  category?: string;
  material?: string;
  size?: string;
  min_price?: number;
  max_price?: number;
  is_new?: boolean;
  is_bestseller?: boolean;
  ordering?: string;
  page?: number;
  page_size?: number;
}

export async function getProducts(
  query: ProductQuery = {},
): Promise<Paginated<ProductListItem>> {
  const qs = buildQuery({
    ...query,
    is_new: query.is_new ? "true" : undefined,
    is_bestseller: query.is_bestseller ? "true" : undefined,
  });
  return apiFetch<Paginated<ProductListItem>>(`/catalog/products${qs}`, {
    revalidate: CATALOG_REVALIDATE,
  });
}

export async function getProduct(slug: string): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/catalog/products/${slug}`, {
    revalidate: CATALOG_REVALIDATE,
  });
}

export async function searchProducts(
  q: string,
  page = 1,
  pageSize = 12,
): Promise<SearchResponse> {
  const qs = buildQuery({ q, page, page_size: pageSize });
  return apiFetch<SearchResponse>(`/search${qs}`, { revalidate: 0 });
}

/**
 * Run a catalog fetch and fall back to a default on any error, so a page still
 * renders (degraded) when the API is unreachable — degraded beats a 500.
 */
export async function safe<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}
