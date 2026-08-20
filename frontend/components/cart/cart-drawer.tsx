"use client";

import { X } from "@phosphor-icons/react";
import Link from "next/link";
import { formatMoney } from "@/lib/format";
import { useCart } from "./cart-provider";

export function CartDrawer() {
  const context = useCart();
  if (!context?.open) return null;
  const { cart, error, loading, setOpen, setQuantity, remove } = context;
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}>
      <aside className="cart-drawer" role="dialog" aria-modal="true" aria-labelledby="cart-drawer-title">
        <div className="drawer-head">
          <h2 id="cart-drawer-title">Tu carrito</h2>
          <button className="icon-button" type="button" aria-label="Cerrar carrito" onClick={() => setOpen(false)}><X size={22} /></button>
        </div>
        {error && <p className="inline-error" role="alert">{error} Volvé a intentarlo.</p>}
        {!cart || cart.lines.length === 0 ? (
          <div className="empty-state"><h3>Tu carrito está listo para empezar</h3><p>Explorá el catálogo y agregá los productos que quieras.</p><Link className="button primary" href="/catalogo" onClick={() => setOpen(false)}>Explorar catálogo</Link></div>
        ) : (
          <>
            <div className="cart-lines">
              {cart.lines.map((line) => (
                <article className="cart-line" key={line.id}>
                  <div><strong>{line.sku}</strong><span>{formatMoney(line.unit_price)} por unidad</span></div>
                  <div className="quantity-control">
                    <button type="button" aria-label={`Reducir cantidad de ${line.sku}`} onClick={() => void setQuantity(line.variant_id, line.quantity - 1)}>-</button>
                    <span aria-live="polite">{line.quantity}</span>
                    <button type="button" aria-label={`Aumentar cantidad de ${line.sku}`} onClick={() => void setQuantity(line.variant_id, line.quantity + 1)}>+</button>
                  </div>
                  <button className="text-button" type="button" onClick={() => void remove(line.variant_id)}>Quitar</button>
                </article>
              ))}
            </div>
            <div className="drawer-total"><span>Total</span><strong>{formatMoney(cart.total)}</strong></div>
            <Link className="button primary wide" href="/carrito" onClick={() => setOpen(false)}>Revisar carrito</Link>
          </>
        )}
        {loading && <p className="loading-note" role="status">Actualizando carrito…</p>}
      </aside>
    </div>
  );
}
