import Link from "next/link";

import { ProductEditorPanel } from "@/components/management/product-editor-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementAttributeDefinition, ManagementBrand, ManagementCategory } from "@/lib/management/catalog-types";


export default async function NewProductPage() {
  const [categories, brands, attributes] = await Promise.all([
    managementServerGet<{ results: ManagementCategory[] }>("/categories/"),
    managementServerGet<{ results: ManagementBrand[] }>("/brands/"),
    managementServerGet<{ results: ManagementAttributeDefinition[] }>("/attributes/"),
  ]);
  return <div className="management-page management-editor-page"><Link className="management-back" href="/gestion/catalogo">← Productos</Link><header className="management-page-header"><div><p className="management-kicker">Catálogo</p><h1>Nuevo producto</h1><p>Cargá la información comercial, física y de stock.</p></div></header>{categories.results.length ? <ProductEditorPanel attributes={attributes.results} brands={brands.results} categories={categories.results} /> : <div className="management-empty"><h2>Primero creá una categoría</h2><Link className="button primary" href="/gestion/categorias">Crear categoría</Link></div>}</div>;
}
