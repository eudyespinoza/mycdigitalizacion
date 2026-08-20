"use client";

import { useState } from "react";
import type { ProductVariant } from "@/lib/types";
import { formatMoney } from "@/lib/format";
import { useCart } from "@/components/cart/cart-provider";

export function ProductPurchase({ productName, variants, onAdd }: { productName: string; variants: ProductVariant[]; onAdd?: (payload: { variant_id: number; quantity: number }) => void | Promise<void> }) {
  const cart = useCart();
  const [variantId, setVariantId] = useState(variants[0]?.id ?? 0);
  const [quantity, setQuantity] = useState(1);
  const [message, setMessage] = useState("");
  const variant = variants.find((item) => item.id === variantId);
  const add = async () => {
    if (!variant) return;
    const payload = { variant_id: variant.id, quantity };
    await (onAdd?.(payload) ?? cart?.add(payload));
    setMessage(`${productName} se agregó al carrito.`);
  };
  if (!variant) return <div className="inline-notice"><strong>Sin variantes disponibles</strong><p>Este producto no se puede agregar por el momento.</p></div>;
  return <div className="purchase-panel"><p className="product-price">{formatMoney(variant.price)}</p><label htmlFor="variant">Variante</label><select id="variant" value={variantId} onChange={(event) => setVariantId(Number(event.target.value))}>{variants.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.sku}</option>)}</select><label htmlFor="quantity">Cantidad</label><input id="quantity" type="number" min={1} value={quantity} onChange={(event) => setQuantity(Math.max(1, Number(event.target.value)))} /><button className="button primary wide" type="button" onClick={() => void add()}>Agregar al carrito</button>{message && <p className="success-message" role="status">{message}</p>}<p className="purchase-note">El precio y la disponibilidad se vuelven a validar al actualizar el carrito.</p></div>;
}
