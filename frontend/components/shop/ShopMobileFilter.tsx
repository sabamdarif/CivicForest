"use client";

import { useState } from "react";
import type { Category } from "@/lib/api/types";
import { MobileFilterDrawer, useActiveFilterCount } from "@/components/shop/ShopFilters";
import { FilterIcon } from "@/components/ui/icons";

export function ShopMobileFilter({ categories }: { categories: Category[] }) {
  const [open, setOpen] = useState(false);
  const activeCount = useActiveFilterCount();

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-sm border border-black/15 bg-white px-3.5 py-2 text-sm font-medium text-ink transition hover:border-charcoal lg:hidden"
      >
        <FilterIcon className="h-4 w-4 text-gold" />
        <span>Filters</span>
        {activeCount > 0 && (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-gold px-1 text-[11px] font-bold text-charcoal">
            {activeCount}
          </span>
        )}
      </button>

      <MobileFilterDrawer
        categories={categories}
        open={open}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
