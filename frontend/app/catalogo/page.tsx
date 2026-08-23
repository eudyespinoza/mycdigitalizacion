import Link from "next/link";
import { CatalogBrowser } from "@/components/catalog/catalog-browser";
import { CatalogContentCarousel } from "@/components/catalog/catalog-content-carousel";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { buildCatalogQuery, type CatalogState } from "@/lib/catalog-query";
import { serverGet } from "@/lib/api";
import type { CatalogContent, CatalogResponse, Category } from "@/lib/types";

export const dynamic = "force-dynamic";
const emptyFacets = { categories: [], brands: [], price: { min: null, max: null }, availability: { in_stock: 0, out_of_stock: 0 }, offer: { on_offer: 0, regular: 0 }, attributes: [] };
const one = (value: string | string[] | undefined) => typeof value === "string" ? value : undefined;

export default async function CatalogPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const attributes = Object.fromEntries(Object.entries(params).filter(([key, value]) => key.startsWith("attribute_") && typeof value === "string").map(([key, value]) => [key.slice(10), String(value).split(",").filter(Boolean)]));
  const initial: CatalogState = { q: one(params.q), category: one(params.category), brands: one(params.brand)?.split(",").filter(Boolean), minPrice: one(params.min_price) ? Number(one(params.min_price)) : undefined, maxPrice: one(params.max_price) ? Number(one(params.max_price)) : undefined, inStock: one(params.availability) === "in_stock" || undefined, onOffer: one(params.offer) === "true" || undefined, attributes, sort: (one(params.ordering) as CatalogState["sort"]) ?? "relevance", page: one(params.page) ? Number(one(params.page)) : 1 };
  let response: CatalogResponse = { count: 0, next: null, previous: null, results: [], facets: emptyFacets };
  let categories: Category[] = []; let catalogContent: CatalogContent = { slides: [] }; let failed = false;
  const [productResult, categoryResult, contentResult] = await Promise.allSettled([
    serverGet<CatalogResponse>(`/products/${buildCatalogQuery(initial) ? `?${buildCatalogQuery(initial)}` : ""}`),
    serverGet<Category[]>("/categories/"),
    serverGet<CatalogContent>("/storefront/catalog-content/"),
  ]);
  if (productResult.status === "fulfilled") response = productResult.value; else failed = true;
  if (categoryResult.status === "fulfilled") categories = categoryResult.value;
  if (contentResult.status === "fulfilled") catalogContent = contentResult.value;
  const fallbackTitle = initial.q ? `Resultados para “${initial.q}”` : "Todo el catálogo";
  return <><SiteHeader categories={categories} /><main id="contenido" className="page-shell shell"><nav className="breadcrumb" aria-label="Migas de pan"><Link href="/">Inicio</Link><span>/</span><span>Catálogo</span></nav><CatalogContentCarousel fallbackBody="Elegí por categoría, marca, precio y disponibilidad." fallbackTitle={fallbackTitle} slides={catalogContent.slides} />{failed ? <div className="empty-state"><h2>No pudimos mostrar el catálogo</h2><p>Reintentá en unos minutos. Tus filtros van a seguir aplicados.</p><a className="button primary" href={`/catalogo${buildCatalogQuery(initial) ? `?${buildCatalogQuery(initial)}` : ""}`}>Reintentar</a></div> : <CatalogBrowser response={response} categories={categories} initial={initial} />}</main><SiteFooter /></>;
}
