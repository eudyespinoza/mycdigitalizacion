"use client";

import { useRouter } from "next/navigation";

import { ManagementProductEditor } from "@/components/management/product-editor";
import { ProductMediaManager } from "@/components/management/product-media-manager";
import { managementRequest } from "@/lib/management/api";
import type {
  ManagementAttributeDefinition,
  ManagementBrand,
  ManagementCategory,
  ManagementProduct,
  ManagementProductMedia,
  ProductEditorPayload,
} from "@/lib/management/catalog-types";


export function ProductEditorPanel({
  categories,
  brands,
  initial,
  attributes,
}: {
  categories: ManagementCategory[];
  brands: ManagementBrand[];
  initial?: ManagementProduct;
  attributes: ManagementAttributeDefinition[];
}) {
  const router = useRouter();
  return <div className="product-editor-layout">
    <ManagementProductEditor
      attributes={attributes}
      brands={brands}
      categories={categories}
      initial={initial}
      onSave={async (payload: ProductEditorPayload) => {
        const saved = await managementRequest<ManagementProduct>(
          initial ? `/products/${initial.id}/` : "/products/",
          { method: initial ? "PATCH" : "POST", body: JSON.stringify(payload) },
        );
        if (!initial) router.replace(`/gestion/catalogo/${saved.id}`);
        router.refresh();
        return saved;
      }}
    />
    <aside className="product-editor-media" aria-label="Galería del producto">
    {initial ? <ProductMediaManager
      initialMedia={initial.media}
      variants={initial.variants}
      onCreate={(form) => managementRequest<ManagementProductMedia>(`/products/${initial.id}/media/`, { method: "POST", body: form })}
      onDelete={(id) => managementRequest<void>(`/products/${initial.id}/media/${id}/`, { method: "DELETE" })}
      onUpdate={(id, form) => managementRequest<ManagementProductMedia>(`/products/${initial.id}/media/${id}/`, { method: "PATCH", body: form })}
    /> : <section className="management-form-section product-editor-media-placeholder"><h2>Imágenes del producto</h2><p>Guardá el producto para cargar sus imágenes y asignarlas a cada variante.</p></section>}
    </aside>
  </div>;
}
