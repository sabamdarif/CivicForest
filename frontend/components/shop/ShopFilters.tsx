"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import type { Category } from "@/lib/api/types";

const SIZES = ["S", "M", "L", "XL"];
const COLORS = [
  ["Black", "#111111"],
  ["Forest Green", "#1F3D2B"],
  ["Navy", "#1B2A4A"],
  ["Beige", "#D8C6A8"],
  ["Heather Grey", "#B8B8B8"],
  ["White", "#F4F1EA"],
];
const MATERIALS = ["Organic Cotton", "Cotton", "Fleece", "Cotton Blend", "French Terry"];

/** Filter sidebar. All state lives in the URL so filters are shareable, SSR-friendly,
 * and the back button works. Selecting a filter resets to page 1. */
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
  const activeColors = (params.get("color") ?? "").split(",").filter(Boolean);
  const activeMaterial = params.get("material");

  const hasFilters = ["category", "size", "color", "material", "min_price", "max_price"].some(
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
            className="text-xs uppercase tracking-brand text-gold hover:underline"
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
              className={`h-9 w-9 rounded-sm border text-sm transition ${
                activeSizes.includes(size)
                  ? "border-charcoal bg-charcoal text-cream"
                  : "border-black/15 text-ink hover:border-charcoal"
              }`}
            >
              {size}
            </button>
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Color">
        <div className="flex flex-wrap gap-2.5">
          {COLORS.map(([name, hex]) => (
            <button
              key={name}
              type="button"
              title={name}
              aria-label={name}
              onClick={() => toggleCsv("color", name)}
              className={`h-7 w-7 rounded-full border-2 transition ${
                activeColors.includes(name) ? "border-gold" : "border-black/10"
              }`}
              style={{ backgroundColor: hex }}
            />
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
