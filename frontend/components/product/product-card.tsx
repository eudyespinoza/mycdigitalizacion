"use client";

import { Minus, Plus, ShoppingCartSimple } from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useCart } from "@/components/cart/cart-provider";
import { normalizeMediaUrl } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { Product } from "@/lib/types";

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const cart = useCart();
  const availableVariants = useMemo(
    () => product.variants.filter((variant) => variant.is_available),
    [product.variants],
  );
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(availableVariants[0]?.id ?? null);
  const [mutation, setMutation] = useState<"add" | "subtract" | null>(null);
  const [error, setError] = useState("");
  const sortedMedia = [...product.media].sort((a, b) => a.order - b.order);
  const media = sortedMedia.find((item) => item.variant_id === null) ?? sortedMedia[0];
  const source = normalizeMediaUrl(media?.file);
  const displayVariant = product.variants.find(
    (variant) => Number(variant.pricing.effective_price) === Number(product.effective_price),
  ) ?? product.variants[0];
  const pricing = displayVariant?.pricing;
  const price = product.effective_price ?? pricing?.effective_price ?? displayVariant?.price;
  const hasDiscount = Boolean(
    product.on_offer
    && pricing?.on_offer
    && Number(pricing.list_price) > Number(pricing.effective_price),
  );
  const discount = pricing
    ? Number(pricing.discount_percentage).toLocaleString("es-AR", { maximumFractionDigits: 2 })
    : "";
  const productVariantIds = useMemo(() => new Set(product.variants.map((variant) => variant.id)), [product.variants]);
  const productCartLines = cart?.cart?.lines.filter((line) => productVariantIds.has(line.variant_id)) ?? [];
  const quantityInCart = productCartLines.reduce((total, line) => total + line.quantity, 0);
  const selectedVariant = availableVariants.find((variant) => variant.id === selectedVariantId) ?? availableVariants[0];
  const unavailable = !product.is_available || availableVariants.length === 0;
  const busy = mutation !== null;

  async function addSelectedVariant() {
    if (!cart || !selectedVariant || busy) return;
    setMutation("add");
    setError("");
    try {
      await cart.add({ variant_id: selectedVariant.id, quantity: 1 }, { openDrawer: false });
      setSelectorOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos agregar el producto al carrito.");
    } finally {
      setMutation(null);
    }
  }

  async function subtractOne() {
    if (!cart || busy || quantityInCart === 0) return;
    const targetLine = productCartLines.find((line) => line.variant_id === selectedVariant?.id)
      ?? productCartLines[productCartLines.length - 1];
    if (!targetLine) return;

    setMutation("subtract");
    setError("");
    try {
      await cart.setQuantity(targetLine.variant_id, Math.max(0, targetLine.quantity - 1));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos restar el producto del carrito.");
    } finally {
      setMutation(null);
    }
  }

  const addDisabled = unavailable || !cart || busy;
  const directLabel = unavailable ? "Sin stock" : mutation === "add" ? "Agregando…" : quantityInCart > 0 ? "Agregar otro" : "Agregar al carrito";
  const quantityControls = quantityInCart > 0 && <>
    <button
      aria-label={`Restar una unidad de ${product.name}`}
      aria-busy={mutation === "subtract"}
      className="product-card-quantity-button"
      disabled={!cart || busy}
      title="Restar una unidad"
      type="button"
      onClick={() => void subtractOne()}
    >
      <Minus aria-hidden="true" size={18} weight="bold" />
    </button>
    <span className="product-card-cart-state" role="status"><span className="product-card-cart-label">En carrito · </span>{quantityInCart}</span>
  </>;
  const addIcon = <span aria-hidden="true" className="product-card-add-icon">
    <ShoppingCartSimple size={23} weight="bold" />
    <Plus className="product-card-add-plus" size={12} weight="bold" />
  </span>;

  return <article aria-label={product.name} className={`product-card${quantityInCart > 0 ? " is-in-cart" : ""}`}>
    <Link className="product-card-link" href={`/producto/${product.slug}`} aria-label={`Ver ${product.name}`}>
      <div className="product-card-media">
        {source
          ? <Image src={source} alt={media.alt_text} fill sizes="(max-width: 640px) 92vw, (max-width: 1024px) 44vw, 24vw" priority={priority} unoptimized />
          : <div className="product-media-empty" aria-hidden><span>{product.name.charAt(0)}</span></div>}
        {hasDiscount && <b className="offer-label">Oferta · {discount}% menos</b>}
      </div>
      <div className="product-card-copy">
        <span>{product.brand?.name || product.category.name}</span>
        <h3>{product.name}</h3>
        {price
          ? <div className="product-card-price">
              {hasDiscount && <del>{formatMoney(pricing!.list_price)}</del>}
              <strong>{formatMoney(price)}</strong>
            </div>
          : <em>Consultá el precio</em>}
        <p className={!product.is_available ? "stock-out" : "stock-in"}>{!product.is_available ? "Sin stock" : "Disponible"}</p>
      </div>
    </Link>
    <div className="product-card-actions">
      {availableVariants.length > 1 && selectorOpen && !unavailable
        ? <div className="product-card-variant-picker">
            <label>
              <span>Opción</span>
              <select
                aria-label={`Opción para ${product.name}`}
                disabled={busy}
                value={selectedVariant?.id ?? ""}
                onChange={(event) => setSelectedVariantId(Number(event.target.value))}
              >
                {availableVariants.map((variant) => <option key={variant.id} value={variant.id}>{variant.name || "Única opción"}</option>)}
              </select>
            </label>
            <div className={`product-card-action-row${quantityInCart === 0 ? " is-empty" : ""}`}>
              {quantityControls}
              <button
                aria-label={mutation === "add" ? "Agregando…" : `Agregar ${selectedVariant?.name || "al carrito"}`}
                aria-busy={mutation === "add"}
                className="product-card-cart-button"
                disabled={addDisabled}
                title={`Agregar ${selectedVariant?.name || "al carrito"}`}
                type="button"
                onClick={() => void addSelectedVariant()}
              >
                {addIcon}
              </button>
            </div>
          </div>
        : availableVariants.length > 1 && !unavailable
          ? <div className={`product-card-action-row${quantityInCart === 0 ? " is-empty" : ""}`}>
              {quantityControls}
              <button
                aria-label={quantityInCart > 0 ? "Agregar otro" : "Elegir opción"}
                className="product-card-cart-button"
                disabled={addDisabled}
                title="Elegir opción para agregar"
                type="button"
                onClick={() => setSelectorOpen(true)}
              >
                {addIcon}
              </button>
            </div>
          : unavailable
            ? <div className={`product-card-action-row${quantityInCart === 0 ? " is-empty" : ""}`}>
                {quantityControls}
                <button className="button product-card-unavailable" disabled type="button">Sin stock</button>
              </div>
            : <div className={`product-card-action-row${quantityInCart === 0 ? " is-empty" : ""}`}>
                {quantityControls}
                <button
                  aria-label={directLabel}
                  aria-busy={mutation === "add"}
                  className="product-card-cart-button"
                  disabled={addDisabled}
                  title={quantityInCart > 0 ? "Agregar otra unidad" : "Agregar al carrito"}
                  type="button"
                  onClick={() => void addSelectedVariant()}
                >
                  {addIcon}
                </button>
              </div>}
      {error && <p className="inline-error product-card-error" role="alert">{error}</p>}
    </div>
  </article>;
}
