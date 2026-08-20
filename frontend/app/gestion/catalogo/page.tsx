import Link from "next/link";

import { ManagementProductTable } from "@/components/management/product-table";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementProduct } from "@/lib/management/catalog-types";


export default async function ManagementCatalogPage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string }>;
}) {
  const { search = "" } = await searchParams;
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const data = await managementServerGet<{ count: number; results: ManagementProduct[] }>(
    `/products/${query}`,
  );
  return (
    <div className="management-page">
      <header className="management-page-header">
        <div><p className="management-kicker">Catálogo</p><h1>Productos</h1><p>{data.count} productos encontrados.</p></div>
        <div className="management-header-actions"><Link className="button secondary" href="/gestion/categorias">Categorías y marcas</Link><Link className="button primary" href="/gestion/catalogo/nuevo">Cargar producto</Link></div>
      </header>
      <form className="management-search"><label><span className="sr-only">Buscar producto o SKU</span><input defaultValue={search} name="search" placeholder="Buscar producto o SKU" type="search" /></label><button className="button secondary" type="submit">Buscar</button></form>
      <ManagementProductTable products={data.results} />
    </div>
  );
}
