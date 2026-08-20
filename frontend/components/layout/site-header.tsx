"use client";

import { List, MagnifyingGlass, ShoppingCartSimple, UserCircle, X } from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { Category } from "@/lib/types";
import { useCart } from "@/components/cart/cart-provider";
import { CartDrawer } from "@/components/cart/cart-drawer";

export function SiteHeader({ categories }: { categories: Category[] }) {
  const [menuOpen, setMenuOpen] = useState(false);
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
          <Link className="brand" href="/" aria-label="mycdigitalizacion, inicio">
            <Image src="/brand/mycdigitalizacion-logo.png" alt="" width={224} height={78} priority />
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
