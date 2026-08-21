"use client";

import { useState } from "react";

import { useCart } from "@/components/cart/cart-provider";
import { formatMoney } from "@/lib/format";
import type { ProductVariant } from "@/lib/types";

export function ProductPurchase({
  productName,
  variants,
  onAdd,
  selectedVariantId,
  onVariantChange,
}: {
  productName: string;
  variants: ProductVariant[];
  onAdd?: (payload: { variant_id: number; quantity: number }) => void | Promise<void>;
  selectedVariantId?: number;
  onVariantChange?: (variantId: number) => void;
}) {
  const cart = useCart();
  const [internalVariantId, setInternalVariantId] = useState(variants[0]?.id ?? 0);
  const [quantity, setQuantity] = useState(1);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const variantId = selectedVariantId ?? internalVariantId;
  const variant = variants.find((item) => item.id === variantId);
  const available = variant?.is_available ?? false;

  const add = async () => {
    if (!variant || !available) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const payload = { variant_id: variant.id, quantity };
      await (onAdd?.(payload) ?? cart?.add(payload));
      setMessage(`${productName} se agregó al carrito.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos agregar el producto. Revisá el stock e intentá nuevamente.");
    } finally {
      setBusy(false);
    }
  };

  if (!variant) return <div className="inline-notice"><strong>Sin variantes disponibles</strong><p>Este producto no se puede agregar por el momento.</p></div>;
  const effective = variant.pricing.effective_price;
  const list = variant.pricing.list_price;
  return (
    <div className="purchase-panel">
      <p className="product-price">{formatMoney(effective)}</p>
      {Number(list) > Number(effective) && <p className="compare-price">Antes {formatMoney(list)} · {variant.pricing.discount_percentage}% menos</p>}
      <label htmlFor="variant">Opción</label>
      <select id="variant" value={variantId} onChange={(event) => {
        const nextId = Number(event.target.value);
        setInternalVariantId(nextId);
        onVariantChange?.(nextId);
        setQuantity(1);
        setError("");
      }}>
        {variants.map((item) => <option value={item.id} key={item.id} disabled={!item.is_available}>{item.name || "Única opción"}{!item.is_available ? " · sin stock" : ""}</option>)}
      </select>
      <label htmlFor="quantity">Cantidad</label>
      <input id="quantity" type="number" min={1} max={variant.purchase_limit ?? undefined} value={quantity} onChange={(event) => {
        const requested = Math.max(1, Number(event.target.value));
        setQuantity(variant.purchase_limit === null ? requested : Math.min(requested, variant.purchase_limit));
      }} />
      <button className="button primary wide" type="button" disabled={busy || !available} onClick={() => void add()}>{busy ? "Agregando…" : available ? "Agregar al carrito" : "Sin stock"}</button>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {message && <p className="success-message" role="status">{message}</p>}
      <p className="purchase-note">Confirmamos el precio y la disponibilidad al agregarlo al carrito.</p>
    </div>
  );
}
