"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiBase } from "@/lib/api/client";
import type { SuggestionHit } from "@/lib/api/types";

const MIN_QUERY_LEN = 2;
const DEBOUNCE_MS = 200;
const CACHE_LIMIT = 20;

interface State {
  hits: SuggestionHit[];
  loading: boolean;
}

/**
 * YouTube-style suggestions without per-keystroke waste (plan.md §7):
 *  - fires only at >= 2 chars, on a trailing debounce
 *  - AbortController cancels the previous in-flight request
 *  - a stale-response guard discards answers to an outdated query
 *  - a last-20 in-memory LRU cache makes retypes/backspaces instant
 */
const cache = new Map<string, SuggestionHit[]>();

export function useSearchSuggestions(query: string): State {
  const [state, setState] = useState<State>({ hits: [], loading: false });

  const abortRef = useRef<AbortController | null>(null);
  const latestQueryRef = useRef("");

  const readCache = useCallback((key: string): SuggestionHit[] | undefined => {
    const value = cache.get(key);
    if (value) {
      // Refresh recency (LRU).
      cache.delete(key);
      cache.set(key, value);
    }
    return value;
  }, []);

  const writeCache = useCallback((key: string, value: SuggestionHit[]) => {
    cache.set(key, value);
    if (cache.size > CACHE_LIMIT) {
      cache.delete(cache.keys().next().value as string);
    }
  }, []);

  const [prevQuery, setPrevQuery] = useState(query);
  if (query !== prevQuery) {
    setPrevQuery(query);
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LEN) {
      setState({ hits: [], loading: false });
    } else {
      const cached = readCache(trimmed.toLowerCase());
      if (cached) {
        setState({ hits: cached, loading: false });
      } else {
        setState((s) => ({ ...s, loading: true }));
      }
    }
  }

  useEffect(() => {
    const trimmed = query.trim();
    latestQueryRef.current = trimmed;

    if (trimmed.length < MIN_QUERY_LEN) {
      abortRef.current?.abort();
      return;
    }

    const cached = readCache(trimmed.toLowerCase());
    if (cached) {
      return;
    }

    const handle = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const url = `${apiBase()}/api/v1/search/suggest?q=${encodeURIComponent(trimmed)}`;
        const res = await fetch(url, {
          signal: controller.signal,
          credentials: "include",
          headers: { Accept: "application/json" },
        });
        if (!res.ok) throw new Error(`suggest ${res.status}`);
        const data = (await res.json()) as { query: string; hits: SuggestionHit[] };

        writeCache(trimmed.toLowerCase(), data.hits);

        // Stale-response guard: only apply if the box still holds this query.
        if (latestQueryRef.current === trimmed) {
          setState({ hits: data.hits, loading: false });
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (latestQueryRef.current === trimmed) {
          setState({ hits: [], loading: false });
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(handle);
  }, [query, readCache, writeCache]);

  return state;
}
