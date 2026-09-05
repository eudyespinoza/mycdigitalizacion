import Link from "next/link";

import { ProductEditorPanel } from "@/components/management/product-editor-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementAttributeDefinition, ManagementBrand, ManagementCategory, ManagementProduct } from "@/lib/management/catalog-types";


export default async function EditProductPage({ params }: { params: Promise<{ productId: string }> }) {
  const { productId } = await params;
  const [product, categories, brands, attributes] = await Promise.all([
    managementServerGet<ManagementProduct>(`/products/${productId}/`),
    managementServerGet<{ results: ManagementCategory[] }>("/categories/"),
    managementServerGet<{ results: ManagementBrand[] }>("/brands/"),
    managementServerGet<{ results: ManagementAttributeDefinition[] }>("/attributes/"),
  ]);
  return <div className="management-page management-product-page"><Link className="management-back" href="/gestion/catalogo">← Productos</Link><header className="management-page-header"><div><h1>{product.name}</h1><p>{product.is_sellable ? "Publicado en la tienda" : "Borrador"}</p></div></header><ProductEditorPanel attributes={attributes.results} brands={brands.results} categories={categories.results} initial={product} /></div>;
}
