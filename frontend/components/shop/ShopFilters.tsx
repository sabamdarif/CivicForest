"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";

import type { Category } from "@/lib/api/types";

const SIZES = ["S", "M", "L", "XL"];
const MATERIALS = ["Organic Cotton", "Cotton", "Fleece", "Cotton Blend", "French Terry"];

/** Helper hook to return total count of active filters from URL searchParams */
export function useActiveFilterCount(): number {
  const params = useSearchParams();
  const filterKeys = ["category", "size", "material", "min_price", "max_price"];
  let count = 0;
  for (const k of filterKeys) {
    const val = params.get(k);
    if (val) {
      if (k === "size") {
        count += val.split(",").filter(Boolean).length;
      } else {
        count += 1;
      }
    }
  }
  return count;
}

/** Filter sidebar component used in desktop layout & mobile drawer */
export function ShopFilters({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const params = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value === null || next.get(key) === value) {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      next.delete("page");
      router.push(`/shop?${next.toString()}`);
    },
    [params, router],
  );

  const toggleCsv = useCallback(
    (key: string, value: string) => {
      const current = (params.get(key) ?? "").split(",").filter(Boolean);
      const next = new URLSearchParams(params.toString());
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      if (updated.length) next.set(key, updated.join(","));
      else next.delete(key);
      next.delete("page");
      router.push(`/shop?${next.toString()}`);
    },
    [params, router],
  );

  const activeCategory = params.get("category");
  const activeSizes = (params.get("size") ?? "").split(",").filter(Boolean);
  const activeMaterial = params.get("material");

  const hasFilters = ["category", "size", "material", "min_price", "max_price"].some(
    (k) => params.get(k),
  );

  return (
    <aside className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-lg text-ink">Filters</h2>
        {hasFilters && (
          <button
            type="button"
            onClick={() => router.push("/shop")}
            className="text-xs font-medium uppercase tracking-brand text-gold hover:underline"
          >
            Clear all
          </button>
        )}
      </div>

      <FilterGroup title="Category">
        <ul className="space-y-2">
          {categories.map((cat) => (
            <li key={cat.id}>
              <button
                type="button"
                onClick={() => setParam("category", cat.slug)}
                className={`flex w-full items-center justify-between text-sm transition ${
                  activeCategory === cat.slug ? "font-semibold text-gold" : "text-ink/70 hover:text-ink"
                }`}
              >
                <span>{cat.name}</span>
                {cat.product_count != null && (
                  <span className="text-xs text-ink/40">{cat.product_count}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </FilterGroup>

      <FilterGroup title="Size">
        <div className="flex flex-wrap gap-2">
          {SIZES.map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => toggleCsv("size", size)}
              className={`h-9 min-w-9 rounded-sm border px-2.5 text-sm transition ${
                activeSizes.includes(size)
                  ? "border-charcoal bg-charcoal text-cream font-medium"
                  : "border-black/15 text-ink hover:border-charcoal"
              }`}
            >
              {size}
            </button>
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Material">
        <ul className="space-y-2">
          {MATERIALS.map((m) => {
            const slug = m.toLowerCase().replace(/\s+/g, "-");
            return (
              <li key={m}>
                <button
                  type="button"
                  onClick={() => setParam("material", slug)}
                  className={`text-sm transition ${
                    activeMaterial === slug ? "font-semibold text-gold" : "text-ink/70 hover:text-ink"
                  }`}
                >
                  {m}
                </button>
              </li>
            );
          })}
        </ul>
      </FilterGroup>
    </aside>
  );
}

/** Mobile Filter Slide-Over Drawer */
export function MobileFilterDrawer({
  categories,
  open,
  onClose,
}: {
  categories: Category[];
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div
        className="fixed inset-0 bg-charcoal/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Filter products"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xs flex-col bg-cream shadow-2xl transition-transform"
      >
        <header className="flex items-center justify-between border-b border-black/10 px-6 py-5">
          <h2 className="font-serif text-xl text-ink">Filters</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close filters"
            className="flex h-8 w-8 items-center justify-center text-ink/60 hover:text-ink"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6 scroll-thin">
          <ShopFilters categories={categories} />
        </div>

        <footer className="border-t border-black/10 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="btn-dark w-full justify-center"
          >
            Show Results
          </button>
        </footer>
      </aside>
    </div>
  );
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-brand text-ink/50">
        {title}
      </h3>
      {children}
    </div>
  );
}
