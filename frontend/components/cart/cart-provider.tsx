"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { cartApi } from "@/lib/api";
import type { Cart } from "@/lib/types";

type CartContextValue = {
  cart: Cart | null;
  loading: boolean;
  open: boolean;
  error: string;
  setOpen: (open: boolean) => void;
  refresh: () => Promise<void>;
  add: (payload: { variant_id: number; quantity: number }) => Promise<void>;
  setQuantity: (variant_id: number, quantity: number) => Promise<void>;
  applyCoupon: (coupon: string) => Promise<void>;
  remove: (variant_id: number) => Promise<void>;
};

const CartContext = createContext<CartContextValue | null>(null);
const TOKEN_KEY = "myc-cart-token";

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const token = () => (typeof window === "undefined" ? null : window.sessionStorage.getItem(TOKEN_KEY));
  const accept = (next: Cart) => {
    setCart(next);
    if (next.cart_token && typeof window !== "undefined") window.sessionStorage.setItem(TOKEN_KEY, next.cart_token);
  };
  const perform = useCallback(async (request: () => Promise<Cart>) => {
    setLoading(true);
    setError("");
    try {
      accept(await request());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos actualizar el carrito.");
      throw cause;
    } finally {
      setLoading(false);
    }
  }, []);
  const refresh = useCallback(() => perform(() => cartApi.get(token())), [perform]);

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, [refresh]);

  const value = useMemo<CartContextValue>(
    () => ({
      cart,
      loading,
      open,
      error,
      setOpen,
      refresh,
      add: async (payload) => {
        await perform(() => cartApi.add(payload, token()));
        setOpen(true);
      },
      setQuantity: (variant_id, quantity) => perform(() => cartApi.quantity({ variant_id, quantity }, token())),
      applyCoupon: (coupon) => perform(() => cartApi.coupon(coupon, token())),
      remove: (variant_id) => perform(() => cartApi.clear(variant_id, token())),
    }),
    [cart, error, loading, open, perform, refresh],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  return useContext(CartContext);
}
