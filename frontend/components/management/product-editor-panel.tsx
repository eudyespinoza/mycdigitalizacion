"use client";

import { useRouter } from "next/navigation";

import { ManagementProductEditor } from "@/components/management/product-editor";
import { managementRequest } from "@/lib/management/api";
import type {
  ManagementBrand,
  ManagementCategory,
  ManagementProduct,
  ProductEditorPayload,
} from "@/lib/management/catalog-types";


export function ProductEditorPanel({
  categories,
  brands,
  initial,
}: {
  categories: ManagementCategory[];
  brands: ManagementBrand[];
  initial?: ManagementProduct;
}) {
  const router = useRouter();
  return (
    <ManagementProductEditor
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
  );
}
