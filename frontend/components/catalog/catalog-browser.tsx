"use client";

import { FunnelSimple, X } from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProductCard } from "@/components/product/product-card";
import { apiRequest } from "@/lib/api";
import {
  buildCatalogQuery,
  parseCatalogQuery,
  type CatalogState,
} from "@/lib/catalog-query";
import type { CatalogResponse, Category } from "@/lib/types";

type HistoryMode = "push" | "none";

function catalogUrl(state: CatalogState) {
  const query = buildCatalogQuery(state);
  return query ? `/catalogo?${query}` : "/catalogo";
}

function catalogApiPath(state: CatalogState) {
  const query = buildCatalogQuery(state);
  return `/products/${query ? `?${query}` : ""}`;
}

export function CatalogBrowser({
  response,
  categories,
  initial,
}: {
  response: CatalogResponse;
  categories: Category[];
  initial: CatalogState;
}) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
  const resultsRef = useRef<HTMLElement>(null);
  const requestRef = useRef(0);
  const confirmedStateRef = useRef(initial);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [catalog, setCatalog] = useState(response);
  const [state, setState] = useState(initial);
  const [pending, setPending] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [minPrice, setMinPrice] = useState(initial.minPrice?.toString() ?? "");
  const [maxPrice, setMaxPrice] = useState(initial.maxPrice?.toString() ?? "");

  useEffect(() => {
    confirmedStateRef.current = initial;
    setState(initial);
    setCatalog(response);
    setMinPrice(initial.minPrice?.toString() ?? "");
    setMaxPrice(initial.maxPrice?.toString() ?? "");
  }, [initial, response]);

  const apply = useCallback(async (next: CatalogState, historyMode: HistoryMode = "push") => {
    const requestId = ++requestRef.current;
    setState(next);
    setMinPrice(next.minPrice?.toString() ?? "");
    setMaxPrice(next.maxPrice?.toString() ?? "");
    setLoadError("");
    setPending(true);
    if (historyMode === "push") window.history.pushState({ catalog: true }, "", catalogUrl(next));

    try {
      const nextCatalog = await apiRequest<CatalogResponse>(catalogApiPath(next));
      if (requestId !== requestRef.current) return;
      confirmedStateRef.current = next;
      setCatalog(nextCatalog);
    } catch {
      if (requestId !== requestRef.current) return;
      const confirmed = confirmedStateRef.current;
      setState(confirmed);
      setMinPrice(confirmed.minPrice?.toString() ?? "");
      setMaxPrice(confirmed.maxPrice?.toString() ?? "");
      window.history.replaceState({ catalog: true }, "", catalogUrl(confirmed));
      setLoadError("No pudimos aplicar ese filtro. Intentá nuevamente.");
    } finally {
      if (requestId === requestRef.current) setPending(false);
    }
  }, []);

  useEffect(() => {
    const restoreFromHistory = () => {
      void apply(parseCatalogQuery(new URLSearchParams(window.location.search)), "none");
    };
    window.addEventListener("popstate", restoreFromHistory);
    return () => window.removeEventListener("popstate", restoreFromHistory);
  }, [apply]);

  const close = () => {
    setFiltersOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  useEffect(() => {
    if (!filtersOpen) return;
    const background = [...document.querySelectorAll<HTMLElement>(
      ".site-header, .trust-rail, .site-footer, .breadcrumb, .catalog-carousel, .catalog-title",
    )];
    background.forEach((item) => item.setAttribute("inert", ""));
    resultsRef.current?.setAttribute("inert", "");
    sheetRef.current?.querySelector<HTMLElement>("button, input, select")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !sheetRef.current) return;
      const nodes = [...sheetRef.current.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), [href]",
      )];
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      background.forEach((item) => item.removeAttribute("inert"));
      resultsRef.current?.removeAttribute("inert");
    };
  }, [filtersOpen]);

  const depth = useMemo(() => {
    const byId = new Map(categories.map((item) => [item.id, item]));
    return new Map(categories.map((item) => {
      let level = 0;
      let parent = item.parent_id ? byId.get(item.parent_id) : undefined;
      while (parent && level < 5) {
        level += 1;
        parent = parent.parent_id ? byId.get(parent.parent_id) : undefined;
      }
      return [item.id, level];
    }));
  }, [categories]);
  const toggle = (values: string[] | undefined, value: string) => values?.includes(value)
    ? values.filter((item) => item !== value)
    : [...(values ?? []), value];
  const chips: Array<{ label: string; clear: () => void }> = [];
  if (state.q) chips.push({ label: `Búsqueda: ${state.q}`, clear: () => void apply({ ...state, q: undefined, page: 1 }) });
  if (state.category) chips.push({ label: categories.find((item) => item.slug === state.category)?.name ?? state.category, clear: () => void apply({ ...state, category: undefined, page: 1 }) });
  state.brands?.forEach((brand) => chips.push({ label: `Marca: ${brand}`, clear: () => void apply({ ...state, brands: state.brands?.filter((item) => item !== brand), page: 1 }) }));
  if (state.inStock) chips.push({ label: "Con stock", clear: () => void apply({ ...state, inStock: undefined, page: 1 }) });
  if (state.onOffer) chips.push({ label: "En oferta", clear: () => void apply({ ...state, onOffer: undefined, page: 1 }) });
  Object.entries(state.attributes ?? {}).forEach(([name, values]) => values.forEach((value) => chips.push({ label: `${name}: ${value}`, clear: () => void apply({ ...state, attributes: { ...state.attributes, [name]: values.filter((item) => item !== value) }, page: 1 }) })));

  return <div className="catalog-layout">
      <button ref={triggerRef} className="filter-trigger button secondary" type="button" onClick={() => setFiltersOpen(true)} aria-expanded={filtersOpen} aria-controls="catalog-filters"><FunnelSimple size={19} /> Filtrar</button>
      <aside ref={sheetRef} id="catalog-filters" className={`filters ${filtersOpen ? "is-open" : ""}`} aria-label="Filtros de catálogo" role={filtersOpen ? "dialog" : undefined} aria-modal={filtersOpen || undefined}>
        <div className="filters-title"><h2>Filtrar</h2><button className="icon-button filter-close" type="button" aria-label="Cerrar filtros" onClick={close}><X size={20} /></button></div>
        <label htmlFor="category-filter">Categoría</label><select id="category-filter" value={state.category ?? ""} onChange={(event) => void apply({ ...state, category: event.target.value || undefined, page: 1 })}><option value="">Todas</option>{categories.map((category) => <option key={category.id} value={category.slug}>{`${"· ".repeat(depth.get(category.id) ?? 0)}${category.name}`}</option>)}</select>
        {catalog.facets.brands.length > 0 && <fieldset><legend>Marca</legend>{catalog.facets.brands.map((option) => <label className="facet-option" key={option.slug}><input type="checkbox" checked={state.brands?.includes(option.slug) ?? false} onChange={() => void apply({ ...state, brands: toggle(state.brands, option.slug), page: 1 })} /> {option.name} <small>({option.count})</small></label>)}</fieldset>}
        <form className="price-filter" onSubmit={(event) => { event.preventDefault(); void apply({ ...state, minPrice: minPrice ? Number(minPrice) : undefined, maxPrice: maxPrice ? Number(maxPrice) : undefined, page: 1 }); }}><fieldset><legend>Precio</legend><div className="field-pair"><div><label htmlFor="min-price">Desde</label><input id="min-price" inputMode="numeric" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} /></div><div><label htmlFor="max-price">Hasta</label><input id="max-price" inputMode="numeric" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} /></div></div><button className="button secondary">Aplicar precio</button></fieldset></form>
        <fieldset><legend>Disponibilidad</legend><label className="facet-option"><input type="checkbox" checked={state.inStock ?? false} onChange={(event) => void apply({ ...state, inStock: event.target.checked || undefined, page: 1 })} /> Con stock <small>({catalog.facets.availability.in_stock})</small></label><label className="facet-option"><input type="checkbox" checked={state.onOffer ?? false} onChange={(event) => void apply({ ...state, onOffer: event.target.checked || undefined, page: 1 })} /> En oferta <small>({catalog.facets.offer.on_offer})</small></label></fieldset>
        {catalog.facets.attributes.map((facet) => <fieldset key={facet.slug}><legend>{facet.name}</legend>{facet.values.map((option) => { const value = String(option.value); return <label className="facet-option" key={value}><input type="checkbox" checked={state.attributes?.[facet.slug]?.includes(value) ?? false} onChange={() => void apply({ ...state, attributes: { ...state.attributes, [facet.slug]: toggle(state.attributes?.[facet.slug], value) }, page: 1 })} /> {option.label} <small>({option.count})</small></label>; })}</fieldset>)}
        {chips.length > 0 && <button type="button" className="text-button" onClick={() => void apply({ sort: state.sort })}>Limpiar filtros</button>}
      </aside>
      <section ref={resultsRef} className={`catalog-results${pending ? " is-updating" : ""}`} aria-live="polite" aria-busy={pending}>
        <div className="catalog-toolbar"><p><strong>{catalog.count}</strong> {catalog.count === 1 ? "producto encontrado" : "productos encontrados"}</p><label htmlFor="sort">Ordenar</label><select id="sort" value={state.sort ?? "relevance"} onChange={(event) => void apply({ ...state, sort: event.target.value as CatalogState["sort"], page: 1 })}><option value="relevance">Relevancia</option><option value="price_asc">Menor precio</option><option value="price_desc">Mayor precio</option><option value="discount_desc">Mayor descuento</option><option value="newest">Más nuevos</option></select></div>
        {pending && <p className="catalog-update-status" role="status">Actualizando resultados…</p>}
        {loadError && <p className="inline-error" role="alert">{loadError}</p>}
        {chips.length > 0 && <div className="filter-chips" aria-label="Filtros aplicados">{chips.map((chip) => <button type="button" key={chip.label} onClick={chip.clear}>{chip.label} <X size={15} aria-hidden /></button>)}</div>}
        {catalog.results.length ? <div className={`product-grid count-${Math.min(catalog.results.length, 4)}`}>{catalog.results.map((product, index) => <ProductCard product={product} key={product.id} priority={index < 2} />)}</div> : <div className="empty-state catalog-empty"><h2>No encontramos resultados</h2><p>Probá con otra búsqueda o quitá alguno de los filtros.</p><button className="button primary" type="button" disabled={pending} onClick={() => void apply({})}>Ver todo el catálogo</button></div>}
        {(catalog.previous || catalog.next) && <nav className="pagination" aria-label="Páginas del catálogo"><button type="button" disabled={!catalog.previous || pending} onClick={() => void apply({ ...state, page: Math.max(1, (state.page ?? 1) - 1) })}>Anterior</button><span>Página {state.page ?? 1}</span><button type="button" disabled={!catalog.next || pending} onClick={() => void apply({ ...state, page: (state.page ?? 1) + 1 })}>Siguiente</button></nav>}
      </section>
    </div>;
}
