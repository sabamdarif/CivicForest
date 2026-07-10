import type { Metadata } from "next";
import Link from "next/link";

import { ProductCard } from "@/components/product/ProductCard";
import { Pagination } from "@/components/shop/Pagination";
import { searchProducts } from "@/lib/api/catalog";
import { safe } from "@/lib/api/catalog";
import type { ProductListItem, SearchResponse, SuggestionHit } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false },
};

const EMPTY: SearchResponse = {
  query: "",
  results: [],
  count: 0,
  page: 1,
  page_size: 12,
};

// Search hits carry the minimal card fields; adapt them to the ProductCard shape.
function toCard(hit: SuggestionHit): ProductListItem {
  return {
    id: hit.id,
    name: hit.name,
    slug: hit.slug,
    category: hit.category ?? "",
    category_slug: hit.category_slug ?? "",
    price_from: hit.price_from != null ? String(hit.price_from) : "0",
    is_new: false,
    is_bestseller: false,
    thumbnail: hit.thumbnail,
    colors: [],
  };
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const query = (sp.q ?? "").trim();
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const pageSize = 12;

  const data =
    query.length >= 2
      ? await safe<SearchResponse>(searchProducts(query, page, pageSize), EMPTY)
      : EMPTY;

  const start = data.count === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, data.count);

  return (
    <>
      <div className="border-b border-black/5 bg-charcoal text-cream">
        <div className="container-page py-12">
          <p className="text-xs text-cream/50">
            Home <span className="mx-1">›</span> Search
          </p>
          <h1 className="mt-2 font-serif text-4xl">
            {query ? (
              <>
                Results for <span className="text-gold">“{query}”</span>
              </>
            ) : (
              "Search"
            )}
          </h1>
        </div>
      </div>

      <div className="container-page py-12">
        {query.length < 2 ? (
          <p className="py-16 text-center text-ink/50">
            Type at least two characters to search the catalog.
          </p>
        ) : data.count === 0 ? (
          <div className="py-16 text-center">
            <p className="text-ink/60">No products found for “{query}”.</p>
            <Link href="/shop" className="btn-outline mt-6">
              Browse all products
            </Link>
          </div>
        ) : (
          <>
            <p className="border-b border-black/10 pb-4 text-sm text-ink/60">
              Showing {start}–{end} of {data.count}
            </p>
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {data.results.map((hit) => (
                <ProductCard key={hit.id} product={toCard(hit)} />
              ))}
            </div>
            <Pagination
              page={page}
              pageSize={pageSize}
              count={data.count}
              searchParams={sp}
              basePath="/search"
            />
          </>
        )}
      </div>
    </>
  );
}
