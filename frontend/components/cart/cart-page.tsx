"use client";

import Link from "next/link";
import { useState } from "react";
import { formatMoney } from "@/lib/format";
import { useCart } from "./cart-provider";

export function CartPage() {
  const context = useCart(); const [coupon, setCoupon] = useState("");
  if (!context || context.loading && !context.cart) return <div className="cart-skeleton" role="status">Actualizando precios y disponibilidad…</div>;
  const { cart, error, loading, setQuantity, remove, applyCoupon, refresh } = context;
  if (!cart || cart.lines.length === 0) return <div className="empty-state page-empty"><h1>Tu carrito está vacío</h1><p>Cuando agregues un producto, lo vas a encontrar acá con sus totales confirmados.</p><Link className="button primary" href="/catalogo">Explorar catálogo</Link></div>;
  return <div className="cart-page-grid"><section><h1>Tu carrito</h1><p className="page-intro">Revalidamos los valores con el servidor cada vez que abrís esta página.</p>{error && <p role="alert" className="inline-error">{error} <button className="text-button" onClick={() => void refresh()}>Reintentar</button></p>}<div className="cart-page-lines">{cart.lines.map((line) => <article key={line.id}><div><strong>{line.sku}</strong><p>{formatMoney(line.unit_price)} por unidad</p></div><label> Cantidad <input type="number" min={0} value={line.quantity} onChange={(event) => void setQuantity(line.variant_id, Number(event.target.value))} /></label><strong>{formatMoney(Number(line.unit_price) * line.quantity)}</strong><button className="text-button" onClick={() => void remove(line.variant_id)}>Quitar</button></article>)}</div></section><aside className="cart-summary"><h2>Resumen</h2><dl><div><dt>Subtotal</dt><dd>{formatMoney(cart.subtotal)}</dd></div><div><dt>Descuento</dt><dd>-{formatMoney(cart.discount)}</dd></div><div className="summary-total"><dt>Total</dt><dd>{formatMoney(cart.total)}</dd></div></dl><form onSubmit={(event) => { event.preventDefault(); void applyCoupon(coupon); }}><label htmlFor="coupon">Cupón</label><div><input id="coupon" value={coupon} onChange={(event) => setCoupon(event.target.value)} /><button className="button secondary" disabled={!coupon || loading}>Aplicar</button></div></form><Link href="/checkout" className="button primary wide">Continuar compra</Link><Link href="/cuenta/ingresar" className="account-prompt">¿Ya tenés cuenta? Ingresá antes de pagar</Link></aside></div>;
}
