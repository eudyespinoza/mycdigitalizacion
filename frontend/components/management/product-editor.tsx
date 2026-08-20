"use client";

import { FormEvent, useState } from "react";

import type {
  ManagementBrand,
  ManagementCategory,
  ManagementProduct,
  ProductEditorPayload,
} from "@/lib/management/catalog-types";


function slugify(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}


export function ManagementProductEditor({
  categories,
  brands,
  initial,
  onSave,
}: {
  categories: ManagementCategory[];
  brands: ManagementBrand[];
  initial?: ManagementProduct;
  onSave: (payload: ProductEditorPayload) => Promise<ManagementProduct>;
}) {
  const variant = initial?.variants[0];
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "");
    const payload: ProductEditorPayload = {
      name,
      slug: String(form.get("slug") || slugify(name)),
      description: String(form.get("description") ?? ""),
      category_id: Number(form.get("category_id")),
      brand_id: form.get("brand_id") ? Number(form.get("brand_id")) : null,
      publish: form.has("publish"),
      variants: [
        {
          ...(variant ? { id: variant.id } : {}),
          sku: String(form.get("sku") ?? ""),
          name: String(form.get("variant_name") ?? ""),
          price: String(form.get("price") ?? ""),
          cost: String(form.get("cost") ?? ""),
          on_hand: Number(form.get("on_hand") ?? 0),
          is_active: true,
          packaged_weight_grams: Number(form.get("packaged_weight_grams") ?? 1),
          length_cm: String(form.get("length_cm") ?? "1"),
          width_cm: String(form.get("width_cm") ?? "1"),
          height_cm: String(form.get("height_cm") ?? "1"),
        },
      ],
    };
    try {
      await onSave(payload);
      setState("saved");
    } catch {
      setState("error");
    }
  };
  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <section className="management-form-section">
        <h2>Información</h2>
        <div className="management-field-grid">
          <label><span>Nombre del producto</span><input defaultValue={initial?.name} name="name" required /></label>
          <label><span>Identificador para la web</span><input defaultValue={initial?.slug} name="slug" placeholder="Se genera desde el nombre" /></label>
          <label><span>Categoría</span><select defaultValue={initial?.category.id ?? categories[0]?.id} name="category_id" required>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label><span>Marca</span><select defaultValue={initial?.brand?.id ?? ""} name="brand_id"><option value="">Sin marca</option>{brands.map((brand) => <option key={brand.id} value={brand.id}>{brand.name}</option>)}</select></label>
          <label className="field-wide"><span>Descripción</span><textarea defaultValue={initial?.description} name="description" rows={5} /></label>
          <label className="management-check field-wide"><input defaultChecked={initial?.is_sellable} name="publish" type="checkbox" /><span>Publicar para la venta</span></label>
        </div>
      </section>
      <section className="management-form-section">
        <h2>Variante principal</h2>
        <p>Después vas a poder agregar colores, tamaños y otras variantes.</p>
        <div className="management-field-grid">
          <label><span>SKU</span><input defaultValue={variant?.sku} name="sku" required /></label>
          <label><span>Nombre de la variante</span><input defaultValue={variant?.name} name="variant_name" /></label>
          <label><span>Precio</span><input defaultValue={variant?.price} min="0" name="price" required step="0.01" type="number" /></label>
          <label><span>Costo</span><input defaultValue={variant?.cost} min="0" name="cost" required step="0.01" type="number" /></label>
          <label><span>Stock inicial</span><input defaultValue={variant?.on_hand ?? 0} min="0" name="on_hand" type="number" /></label>
          <label><span>Peso embalado (gramos)</span><input defaultValue={variant?.packaged_weight_grams ?? 1} min="1" name="packaged_weight_grams" type="number" /></label>
          <label><span>Largo (cm)</span><input defaultValue={variant?.length_cm ?? "1"} min="0.01" name="length_cm" step="0.01" type="number" /></label>
          <label><span>Ancho (cm)</span><input defaultValue={variant?.width_cm ?? "1"} min="0.01" name="width_cm" step="0.01" type="number" /></label>
          <label><span>Alto (cm)</span><input defaultValue={variant?.height_cm ?? "1"} min="0.01" name="height_cm" step="0.01" type="number" /></label>
        </div>
      </section>
      {state === "saved" && <p className="success-message">Producto guardado.</p>}
      {state === "error" && <p className="inline-error">No pudimos guardar el producto. Revisá los campos.</p>}
      <button className="button primary" disabled={state === "saving" || !categories.length} type="submit">
        {state === "saving" ? "Guardando…" : "Guardar producto"}
      </button>
    </form>
  );
}
