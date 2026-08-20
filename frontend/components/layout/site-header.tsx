"use client";

import { List, MagnifyingGlass, ShoppingCartSimple, UserCircle, X } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import type { Category } from "@/lib/types";
import { useCart } from "@/components/cart/cart-provider";
import { CartDrawer } from "@/components/cart/cart-drawer";
import { useBranding } from "@/components/layout/brand-provider";
import { normalizeMediaUrl } from "@/lib/api";
import type { StorefrontSettings } from "@/lib/types";

function BrandImage({ branding, sizes }: { branding: StorefrontSettings; sizes: string }) {
  const logo = normalizeMediaUrl(branding.logo_url) || "/brand/mycdigitalizacion-logo.png";
  const sources = branding.logo_responsive_sources;
  const srcSet = (format: "avif" | "webp" | "fallback") => sources.map((source) => {
    const value = normalizeMediaUrl(source[format]);
    return value ? `${value} ${source.width}w` : "";
  }).filter(Boolean).join(", ");
  const avif = srcSet("avif");
  const webp = srcSet("webp");
  const fallback = srcSet("fallback");
  return <picture className="brand-lockup-media">{avif && <source type="image/avif" srcSet={avif} sizes={sizes} />}{webp && <source type="image/webp" srcSet={webp} sizes={sizes} />}{fallback && <source data-format="fallback" srcSet={fallback} sizes={sizes} />}<img className="brand-logo" src={logo} alt="" loading="eager" decoding="async" fetchPriority="high" /></picture>;
}

export function SiteHeader({ categories, branding: brandingOverride }: { categories: Category[]; branding?: StorefrontSettings }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const contextBranding = useBranding();
  const branding = brandingOverride ?? contextBranding;
  const cart = useCart();
  const count = cart?.cart?.lines.reduce((sum, line) => sum + line.quantity, 0) ?? 0;
  return (
    <>
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <div className="trust-rail" aria-label="Beneficios de compra">
        <span>Envíos a todo el país</span><span>Pagos por Mercado Pago</span><span>Retiro configurable</span>
      </div>
      <header className="site-header">
        <div className="header-main shell">
          <Link className="brand" href="/" aria-label={`${branding.public_name}, inicio`}>
            <BrandImage branding={branding} sizes="(max-width: 420px) 182px, (max-width: 768px) 210px, 270px" />
          </Link>
          <form className="header-search" role="search" action="/catalogo">
            <label className="sr-only" htmlFor="site-search">Buscar productos</label>
            <input id="site-search" name="q" type="search" placeholder="Buscar productos" />
            <button type="submit" aria-label="Buscar"><MagnifyingGlass size={22} /></button>
          </form>
          <div className="header-actions">
            <Link href="/cuenta" aria-label="Mi cuenta"><UserCircle size={26} /><span>Mi cuenta</span></Link>
            <Link href="/carrito" aria-label={`Carrito, ${count} productos`} onClick={(event) => { event.preventDefault(); cart?.setOpen(true); }}>
              <ShoppingCartSimple size={27} /><span>Carrito</span>{count > 0 && <b>{count}</b>}
            </Link>
          </div>
          <button className="mobile-menu-button" type="button" aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={24} /> : <List size={24} />}</button>
        </div>
        <nav className={`category-nav ${menuOpen ? "is-open" : ""}`} aria-label="Categorías principales">
          <div className="shell category-nav-inner">
            <Link href="/catalogo"><List size={19} /> Todo el catálogo</Link>
            {categories.slice(0, 6).map((category) => <Link key={category.id} href={`/catalogo?category=${category.slug}`}>{category.name}</Link>)}
          </div>
        </nav>
      </header>
      <CartDrawer />
    </>
  );
}
