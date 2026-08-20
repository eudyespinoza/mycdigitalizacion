import Link from "next/link";

import { TaxonomyPanel } from "@/components/management/taxonomy-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementAttributeDefinition, ManagementBrand, ManagementCategory } from "@/lib/management/catalog-types";


export default async function TaxonomyPage() {
  const [categories, brands, attributes] = await Promise.all([managementServerGet<{ results: ManagementCategory[] }>("/categories/"), managementServerGet<{ results: ManagementBrand[] }>("/brands/"), managementServerGet<{ results: ManagementAttributeDefinition[] }>("/attributes/")]);
  return <div className="management-page"><Link className="management-back" href="/gestion/catalogo">← Productos</Link><header className="management-page-header"><div><p className="management-kicker">Catálogo</p><h1>Categorías, marcas y atributos</h1><p>Organizá la clasificación y los filtros que usa la tienda.</p></div></header><div className="management-content-gap"><TaxonomyPanel initialAttributes={attributes.results} initialBrands={brands.results} initialCategories={categories.results} /></div></div>;
}
