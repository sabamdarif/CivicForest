"use client";

import { useRouter, useSearchParams } from "next/navigation";

const OPTIONS = [
  ["-created_at", "Newest"],
  ["base_price", "Price: Low to High"],
  ["-base_price", "Price: High to Low"],
  ["name", "Name: A–Z"],
];

export function SortSelect() {
  const router = useRouter();
  const params = useSearchParams();
  const current = params.get("ordering") ?? "-created_at";

  function onChange(value: string) {
    const next = new URLSearchParams(params.toString());
    next.set("ordering", value);
    next.delete("page");
    router.push(`/shop?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-sm text-ink/60">
      Sort by
      <select
        value={current}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-sm border border-black/15 bg-cream px-3 py-1.5 text-ink focus:border-charcoal focus:outline-none"
      >
        {OPTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}
