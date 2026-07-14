"use client";

// App-wide wishlist state. Loads the user's wishlisted product ids once, then lets any
// heart button read/toggle membership without refetching. Wishlist requires auth: a 401
// on load simply means "signed out" and toggles redirect to /login.

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { ApiError } from "@/lib/api/client";
import * as wishlistApi from "@/lib/api/wishlist";
import type { WishlistEntry } from "@/lib/api/types";

interface WishlistContextValue {
  ids: Set<string>;
  authenticated: boolean;
  has: (productId: string) => boolean;
  toggle: (productId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const WishlistContext = createContext<WishlistContextValue | null>(null);

export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ids, setIds] = useState<Set<string>>(new Set());
  const [authenticated, setAuthenticated] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const entries: WishlistEntry[] = await wishlistApi.getWishlist();
      setIds(new Set(entries.map((e) => e.product_id)));
      setAuthenticated(true);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setAuthenticated(false);
        setIds(new Set());
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const has = useCallback((productId: string) => ids.has(productId), [ids]);

  const toggle = useCallback(
    async (productId: string) => {
      if (!authenticated) {
        router.push("/login");
        return;
      }
      // Optimistic flip, reconciled with the server's authoritative answer.
      setIds((prev) => {
        const next = new Set(prev);
        if (next.has(productId)) next.delete(productId);
        else next.add(productId);
        return next;
      });
      try {
        const wishlisted = await wishlistApi.toggleWishlist(productId);
        setIds((prev) => {
          const next = new Set(prev);
          if (wishlisted) next.add(productId);
          else next.delete(productId);
          return next;
        });
      } catch {
        void refresh(); // fall back to server truth on failure
      }
    },
    [authenticated, refresh, router],
  );

  return (
    <WishlistContext.Provider value={{ ids, authenticated, has, toggle, refresh }}>
      {children}
    </WishlistContext.Provider>
  );
}

export function useWishlist(): WishlistContextValue {
  const ctx = useContext(WishlistContext);
  if (!ctx) throw new Error("useWishlist must be used within a WishlistProvider");
  return ctx;
}
