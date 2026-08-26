"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, cartApi } from "@/lib/api";
import { createSerializedQueue } from "@/lib/mutation-queue";
import type { Cart } from "@/lib/types";

type CartAddOptions = { openDrawer?: boolean };
type CartContextValue = { cart: Cart | null; loading: boolean; open: boolean; error: string; setOpen: (open: boolean) => void; restoreFocus: () => void; refresh: () => Promise<void>; add: (payload: { variant_id: number; quantity: number }, options?: CartAddOptions) => Promise<void>; setQuantity: (variant_id: number, quantity: number) => Promise<void>; applyCoupon: (coupon: string) => Promise<void>; remove: (variant_id: number) => Promise<void>; clear: () => Promise<void> };
const CartContext = createContext<CartContextValue | null>(null); const TOKEN_KEY = "myc-cart-token";

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null); const [pending, setPending] = useState(0); const [open, setOpenState] = useState(false); const [error, setError] = useState(""); const queue = useRef(createSerializedQueue()); const opener = useRef<HTMLElement | null>(null);
  const token = () => typeof window === "undefined" ? null : window.sessionStorage.getItem(TOKEN_KEY);
  const accept = (next: Cart) => { setCart(next); if (next.cart_token && typeof window !== "undefined") window.sessionStorage.setItem(TOKEN_KEY, next.cart_token); };
  const perform = useCallback(async (request: () => Promise<Cart>) => { setPending((value) => value + 1); setError(""); try { await queue.current.enqueue(async () => accept(await request())); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos actualizar el carrito."); throw cause; } finally { setPending((value) => Math.max(0, value - 1)); } }, []);
  const refresh = useCallback(async () => {
    try {
      await perform(() => cartApi.get(token()));
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "cart_not_found") {
        sessionStorage.removeItem(TOKEN_KEY);
        setCart(null);
        return;
      }
      throw cause;
    }
  }, [perform]);
  const setOpen = useCallback((next: boolean) => { if (next && document.activeElement instanceof HTMLElement) opener.current = document.activeElement; setOpenState(next); }, []);
  const restoreFocus = useCallback(() => requestAnimationFrame(() => opener.current?.focus()), []);
  useEffect(() => { void refresh().catch(() => undefined); }, [refresh]);
  const value = useMemo<CartContextValue>(() => ({ cart, loading: pending > 0, open, error, setOpen, restoreFocus, refresh, add: async (payload, options) => { const active = document.activeElement instanceof HTMLElement ? document.activeElement : null; await perform(() => cartApi.add(payload, token())); if (options?.openDrawer === false) return; opener.current = active; setOpenState(true); }, setQuantity: (variant_id, quantity) => perform(() => cartApi.quantity({ variant_id, quantity }, token())), applyCoupon: (coupon) => perform(() => cartApi.coupon(coupon, token())), remove: (variant_id) => perform(() => cartApi.clear(variant_id, token())), clear: () => perform(() => cartApi.clear(undefined, token())) }), [cart, pending, open, error, perform, refresh, restoreFocus, setOpen]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
export function useCart() { return useContext(CartContext); }
