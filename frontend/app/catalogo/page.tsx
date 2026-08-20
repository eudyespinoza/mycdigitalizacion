import Link from "next/link";
import { CatalogBrowser } from "@/components/catalog/catalog-browser";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { serverGet } from "@/lib/api";
import type { Category, Product } from "@/lib/types";
import type { CatalogState } from "@/lib/catalog-query";

export const dynamic = "force-dynamic";
export default async function CatalogPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams; const q = typeof params.q === "string" ? params.q : ""; const category = typeof params.category === "string" ? params.category : ""; const sort = typeof params.sort === "string" ? params.sort as CatalogState["sort"] : "relevance"; const page = typeof params.page === "string" ? Number(params.page) : 1;
  let products: Product[] = []; let categories: Category[] = []; let failed = false;
  try { [products, categories] = await Promise.all([serverGet<Product[]>(q ? `/search/?q=${encodeURIComponent(q)}${category ? `&category=${encodeURIComponent(category)}` : ""}` : `/products/${category ? `?category=${encodeURIComponent(category)}` : ""}`), serverGet<Category[]>("/categories/")]); } catch { failed = true; }
  return <><SiteHeader categories={categories} /><main id="contenido" className="page-shell shell"><nav className="breadcrumb" aria-label="Migas de pan"><Link href="/">Inicio</Link><span>/</span><span>Catálogo</span></nav><div className="catalog-title"><h1>{q ? `Resultados para “${q}”` : "Todo el catálogo"}</h1><p>Buscá y filtrá sobre la información publicada por la tienda.</p></div>{failed ? <div className="empty-state"><h2>No pudimos cargar el catálogo</h2><p>Revisá tu conexión e intentá nuevamente.</p><a className="button primary" href="/catalogo">Reintentar</a></div> : <CatalogBrowser products={products} categories={categories} initial={{ q, category, sort, page }} />}</main><SiteFooter /></>;
}
