import type { Metadata } from "next";

import { ProductCard } from "@/components/product/ProductCard";
import { Pagination } from "@/components/shop/Pagination";
import { ShopFilters } from "@/components/shop/ShopFilters";
import { ShopMobileFilter } from "@/components/shop/ShopMobileFilter";
import { SortSelect } from "@/components/shop/SortSelect";
import { getCategories, getProducts, safe } from "@/lib/api/catalog";
import type { Category, Paginated, ProductListItem } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Shop",
  description: "Browse the full CivicForest range — tees, hoodies, sweatshirts and more.",
};

type SearchParams = Record<string, string | undefined>;

const EMPTY: Paginated<ProductListItem> = {
  count: 0,
  next: null,
  previous: null,
  results: [],
};

export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const pageSize = 12;

  const [categories, products] = await Promise.all([
    safe<Category[]>(getCategories(), []),
    safe<Paginated<ProductListItem>>(
      getProducts({
        category: sp.category,
        material: sp.material,
        size: sp.size,
        color: sp.color,
        min_price: sp.min_price ? Number(sp.min_price) : undefined,
        max_price: sp.max_price ? Number(sp.max_price) : undefined,
        is_new: sp.is_new === "true",
        ordering: sp.ordering,
        page,
        page_size: pageSize,
      }),
      EMPTY,
    ),
  ]);

  const start = products.count === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, products.count);

  return (
    <>
      {/* Page header */}
      <div className="border-b border-black/5 bg-charcoal text-cream">
        <div className="container-page py-8 sm:py-12">
          <p className="text-xs text-cream/50">
            Home <span className="mx-1">›</span> Shop
          </p>
          <h1 className="mt-2 font-serif text-3xl sm:text-4xl">Shop All</h1>
          <p className="mt-2 text-sm sm:text-base text-cream/60">
            Timeless styles, premium fabrics — crafted for every version of you.
          </p>
        </div>
      </div>

      <div className="container-page grid gap-10 py-8 sm:py-12 lg:grid-cols-[240px_1fr]">
        <div className="hidden lg:block">
          <ShopFilters categories={categories} />
        </div>

        <div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/10 pb-4">
            <div className="flex items-center gap-3">
              <ShopMobileFilter categories={categories} />
              <p className="text-xs sm:text-sm text-ink/60">
                {products.count > 0
                  ? `Showing ${start}–${end} of ${products.count}`
                  : "No products match your filters"}
              </p>
            </div>
            <SortSelect />
          </div>

          {products.results.length > 0 ? (
            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-3 sm:gap-5">
              {products.results.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          ) : (
            <p className="mt-16 text-center text-ink/50">
              Try clearing a filter or two.
            </p>
          )}

          <Pagination
            page={page}
            pageSize={pageSize}
            count={products.count}
            searchParams={sp}
          />
        </div>
      </div>
    </>
  );
}

