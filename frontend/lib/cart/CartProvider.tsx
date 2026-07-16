"use client";

// App-wide cart state. One provider mounted at the root so the header badge, cart
// drawer, cart page and checkout all read the same server-priced cart. Every mutation
// returns the freshly re-priced cart from the server and replaces local state with it —
// we never do money math in the browser (plan.md §10).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import * as cartApi from "@/lib/api/cart";
import type { Cart } from "@/lib/api/types";

interface CartContextValue {
  cart: Cart | null;
  loading: boolean;
  itemCount: number;
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  refresh: () => Promise<void>;
  addItem: (variantId: string, quantity?: number) => Promise<Cart>;
  setQuantity: (variantId: string, quantity: number) => Promise<Cart>;
  removeItem: (variantId: string) => Promise<Cart>;
  applyCoupon: (code: string) => Promise<Cart>;
  removeCoupon: () => Promise<Cart>;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setCart(await cartApi.getCart());
    } catch {
      // A missing/unavailable cart shouldn't blank the whole app; leave last state.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Async load on mount — state is set in a later microtask, not a sync cascade.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  // Each mutation replaces state with the server's re-priced cart and rethrows on
  // failure so callers can surface the (already user-safe) error message.
  const run = useCallback(async (op: () => Promise<Cart>): Promise<Cart> => {
    const next = await op();
    setCart(next);
    return next;
  }, []);

  const addItem = useCallback(
    async (variantId: string, quantity = 1) => {
      const next = await run(() => cartApi.addCartItem(variantId, quantity));
      setDrawerOpen(true);
      return next;
    },
    [run],
  );

  const setQuantity = useCallback(
    (variantId: string, quantity: number) =>
      run(() => cartApi.setCartItemQuantity(variantId, quantity)),
    [run],
  );

  const removeItem = useCallback(
    (variantId: string) => run(() => cartApi.removeCartItem(variantId)),
    [run],
  );

  const applyCoupon = useCallback(
    (code: string) => run(() => cartApi.applyCoupon(code)),
    [run],
  );

  const removeCoupon = useCallback(
    () => run(() => cartApi.removeCoupon()),
    [run],
  );

  const value: CartContextValue = {
    cart,
    loading,
    itemCount: cart?.item_count ?? 0,
    drawerOpen,
    openDrawer: () => setDrawerOpen(true),
    closeDrawer: () => setDrawerOpen(false),
    refresh,
    addItem,
    setQuantity,
    removeItem,
    applyCoupon,
    removeCoupon,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within a CartProvider");
  return ctx;
}
