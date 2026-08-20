"use client";

import { FunnelSimple, X } from "@phosphor-icons/react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Category, Product } from "@/lib/types";
import { buildCatalogQuery, type CatalogState } from "@/lib/catalog-query";
import { ProductCard } from "@/components/product/product-card";

export function CatalogBrowser({ products, categories, initial }: { products: Product[]; categories: Category[]; initial: CatalogState }) {
  const router = useRouter();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [state, setState] = useState(initial);
  const sorted = useMemo(() => [...products].sort((a, b) => {
    if (state.sort === "price_asc") return Number(a.variants[0]?.price ?? Infinity) - Number(b.variants[0]?.price ?? Infinity);
    if (state.sort === "price_desc") return Number(b.variants[0]?.price ?? -Infinity) - Number(a.variants[0]?.price ?? -Infinity);
    return a.name.localeCompare(b.name, "es");
  }), [products, state.sort]);
  const page = Math.max(1, state.page ?? 1);
  const pageSize = 12;
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const visible = sorted.slice((page - 1) * pageSize, page * pageSize);
  const apply = (next: CatalogState) => { setState(next); const query = buildCatalogQuery(next); router.push(query ? `/catalogo?${query}` : "/catalogo"); };
  return <div className="catalog-layout"><button className="filter-trigger button secondary" onClick={() => setFiltersOpen(true)}><FunnelSimple size={19} /> Filtrar</button><aside className={`filters ${filtersOpen ? "is-open" : ""}`} aria-label="Filtros de catálogo"><div className="filters-title"><h2>Filtrar</h2><button className="icon-button filter-close" aria-label="Cerrar filtros" onClick={() => setFiltersOpen(false)}><X size={20} /></button></div><label htmlFor="category-filter">Categoría</label><select id="category-filter" value={state.category ?? ""} onChange={(event) => apply({ ...state, category: event.target.value, page: 1 })}><option value="">Todas</option>{categories.map((category) => <option key={category.id} value={category.slug}>{category.name}</option>)}</select><p className="filter-note">La API pública actual permite filtrar por categoría y búsqueda. Disponibilidad, marca y atributos aparecerán cuando el contrato los publique.</p>{(state.q || state.category) && <button type="button" className="text-button" onClick={() => apply({ sort: state.sort })}>Limpiar filtros</button>}</aside><section className="catalog-results" aria-live="polite"><div className="catalog-toolbar"><p><strong>{products.length}</strong> productos encontrados</p><label htmlFor="sort">Ordenar</label><select id="sort" value={state.sort ?? "relevance"} onChange={(event) => apply({ ...state, sort: event.target.value as CatalogState["sort"], page: 1 })}><option value="relevance">Nombre</option><option value="price_asc">Menor precio</option><option value="price_desc">Mayor precio</option></select></div>{visible.length ? <div className="product-grid">{visible.map((product) => <ProductCard product={product} key={product.id} />)}</div> : <div className="empty-state catalog-empty"><h2>No encontramos resultados</h2><p>Probá con otra búsqueda o quitá la categoría seleccionada.</p><button className="button primary" onClick={() => apply({})}>Ver todo el catálogo</button></div>} {totalPages > 1 && <nav className="pagination" aria-label="Páginas del catálogo"><button disabled={page <= 1} onClick={() => apply({ ...state, page: page - 1 })}>Anterior</button><span>Página {page} de {totalPages}</span><button disabled={page >= totalPages} onClick={() => apply({ ...state, page: page + 1 })}>Siguiente</button></nav>}</section></div>;
}
