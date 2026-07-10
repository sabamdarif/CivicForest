import Link from "next/link";

import { Monogram } from "./Monogram";

/**
 * Stacked brand lockup: cF monogram over the CIVICFOREST wordmark and a
 * "— CLOTHING —" line, matching the header/footer treatment in the mockups.
 */
export function Logo({
  className = "",
  variant = "gold",
  compact = false,
}: {
  className?: string;
  variant?: "gold" | "cream" | "ink";
  compact?: boolean;
}) {
  const color =
    variant === "gold" ? "text-gold" : variant === "cream" ? "text-cream" : "text-ink";

  return (
    <Link
      href="/"
      aria-label="CivicForest home"
      className={`flex flex-col items-center ${color} ${className}`}
    >
      <Monogram className={compact ? "h-7 w-7" : "h-9 w-9"} />
      <span
        className={`mt-1 font-serif ${compact ? "text-base" : "text-xl"} tracking-brand`}
      >
        CIVICFOREST
      </span>
      {!compact && (
        <span className="mt-0.5 flex items-center gap-1.5 text-[9px] tracking-brand opacity-90">
          <span className="h-px w-3 bg-current" />
          CLOTHING
          <span className="h-px w-3 bg-current" />
        </span>
      )}
    </Link>
  );
}
