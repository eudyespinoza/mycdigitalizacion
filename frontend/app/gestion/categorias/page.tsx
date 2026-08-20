import Link from "next/link";

import { TaxonomyPanel } from "@/components/management/taxonomy-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementBrand, ManagementCategory } from "@/lib/management/catalog-types";


export default async function TaxonomyPage() {
  const [categories, brands] = await Promise.all([managementServerGet<{ results: ManagementCategory[] }>("/categories/"), managementServerGet<{ results: ManagementBrand[] }>("/brands/")]);
  return <div className="management-page"><Link className="management-back" href="/gestion/catalogo">← Productos</Link><header className="management-page-header"><div><p className="management-kicker">Catálogo</p><h1>Categorías y marcas</h1><p>Organizá el catálogo con una jerarquía clara.</p></div></header><div className="management-content-gap"><TaxonomyPanel initialBrands={brands.results} initialCategories={categories.results} /></div></div>;
}
