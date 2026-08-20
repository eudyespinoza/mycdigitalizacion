"use client";

import { useState } from "react";
import type { ProductVariant } from "@/lib/types";
import { formatMoney } from "@/lib/format";
import { useCart } from "@/components/cart/cart-provider";

export function ProductPurchase({ productName, variants, onAdd }: { productName: string; variants: ProductVariant[]; onAdd?: (payload: { variant_id: number; quantity: number }) => void | Promise<void> }) {
  const cart = useCart(); const [variantId, setVariantId] = useState(variants[0]?.id ?? 0); const [quantity, setQuantity] = useState(1); const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const variant = variants.find((item) => item.id === variantId); const available = (variant?.available_stock ?? 0) > 0;
  const add = async () => { if (!variant || !available) return; setBusy(true); setError(""); setMessage(""); try { const payload = { variant_id: variant.id, quantity }; await (onAdd?.(payload) ?? cart?.add(payload)); setMessage(`${productName} se agregó al carrito.`); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos agregar el producto. Revisá el stock e intentá nuevamente."); } finally { setBusy(false); } };
  if (!variant) return <div className="inline-notice"><strong>Sin variantes disponibles</strong><p>Este producto no se puede agregar por el momento.</p></div>;
  const effective = variant.pricing.effective_price; const list = variant.pricing.list_price;
  return <div className="purchase-panel"><p className="product-price">{formatMoney(effective)}</p>{Number(list) > Number(effective) && <p className="compare-price">Antes {formatMoney(list)} · {variant.pricing.discount_percentage}% menos</p>}<label htmlFor="variant">Opción</label><select id="variant" value={variantId} onChange={(event) => { setVariantId(Number(event.target.value)); setError(""); }}>{variants.map((item) => <option value={item.id} key={item.id} disabled={item.available_stock <= 0}>{item.name || "Única opción"}{item.available_stock <= 0 ? " · sin stock" : ""}</option>)}</select><label htmlFor="quantity">Cantidad</label><input id="quantity" type="number" min={1} max={variant.available_stock} value={quantity} onChange={(event) => setQuantity(Math.max(1, Number(event.target.value)))} /><button className="button primary wide" type="button" disabled={busy || !available} onClick={() => void add()}>{busy ? "Agregando…" : available ? "Agregar al carrito" : "Sin stock"}</button>{error && <p className="inline-error" role="alert">{error}</p>}{message && <p className="success-message" role="status">{message}</p>}<p className="purchase-note">Confirmamos el precio y la disponibilidad al agregarlo al carrito.</p></div>;
}
