"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { SearchIcon } from "@/components/ui/icons";
import { formatPrice } from "@/lib/brand/format";
import { useSearchSuggestions } from "@/lib/search/useSearchSuggestions";

/**
 * Full-width search overlay dropped from the header. Owns the input, renders the
 * suggestion dropdown, and supports arrow-key + Enter navigation (plan.md §7).
 */
export function SearchOverlay({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const { hits, loading } = useSearchSuggestions(query);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(-1);
      // Focus after the panel mounts.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActive(-1);
  }, [hits]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function go(target: string) {
    onClose();
    router.push(target);
  }

  function submit() {
    if (active >= 0 && hits[active]) {
      go(`/product/${hits[active].slug}`);
    } else if (query.trim().length >= 2) {
      go(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="absolute inset-x-0 top-full border-t border-cream/10 bg-charcoal/98 backdrop-blur">
      {/* Click-away backdrop */}
      <div
        className="fixed inset-0 top-20 -z-10 bg-black/30"
        aria-hidden
        onClick={onClose}
      />
      <div className="container-page py-5">
        <div className="flex items-center gap-3 border-b border-cream/20 pb-3">
          <SearchIcon className="h-5 w-5 text-gold" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search for tees, hoodies, colors…"
            aria-label="Search products"
            className="w-full bg-transparent text-lg text-cream placeholder:text-cream/40 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="text-xs uppercase tracking-brand text-cream/60 hover:text-gold"
          >
            Esc
          </button>
        </div>

        {query.trim().length >= 2 && (
          <div className="scroll-thin mt-3 max-h-96 overflow-y-auto">
            {loading && hits.length === 0 && (
              <p className="py-6 text-center text-sm text-cream/50">Searching…</p>
            )}
            {!loading && hits.length === 0 && (
              <p className="py-6 text-center text-sm text-cream/50">
                No matches for “{query}”. Press Enter to search anyway.
              </p>
            )}
            <ul>
              {hits.map((hit, i) => (
                <li key={hit.id}>
                  <button
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(`/product/${hit.slug}`)}
                    className={`flex w-full items-center gap-4 rounded-sm px-3 py-2.5 text-left transition ${
                      active === i ? "bg-cream/10" : "hover:bg-cream/5"
                    }`}
                  >
                    <span className="relative h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-charcoal-600">
                      {hit.thumbnail && (
                        <Image
                          src={hit.thumbnail}
                          alt={hit.name}
                          fill
                          sizes="48px"
                          className="object-cover"
                        />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-cream">
                        {hit.name}
                      </span>
                      {hit.category && (
                        <span className="block text-xs text-cream/50">
                          {hit.category}
                        </span>
                      )}
                    </span>
                    {hit.price_from != null && (
                      <span className="text-sm text-gold">
                        {formatPrice(hit.price_from)}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
            {hits.length > 0 && (
              <button
                type="button"
                onClick={() => go(`/search?q=${encodeURIComponent(query.trim())}`)}
                className="mt-2 block w-full rounded-sm px-3 py-2.5 text-left text-sm text-gold hover:bg-cream/5"
              >
                See all results for “{query}” →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
