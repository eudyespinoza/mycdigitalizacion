"use client";

import { FormEvent, useState } from "react";

import type {
  ManagementAttributeDefinition,
  ManagementBrand,
  ManagementCategory,
  ManagementProduct,
  ManagementVariant,
  ProductEditorPayload,
} from "@/lib/management/catalog-types";

function slugify(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

type VariantDraft = {
  key: string;
  id?: number;
  sku: string;
  name: string;
  price: string;
  cost: string;
  on_hand: string;
  is_active: boolean;
  packaged_weight_grams: string;
  length_cm: string;
  width_cm: string;
  height_cm: string;
  attribute_values: Record<number, string>;
};

function draftFromVariant(variant?: ManagementVariant, key = "new-1"): VariantDraft {
  return {
    key: variant ? `variant-${variant.id}` : key,
    ...(variant ? { id: variant.id } : {}),
    sku: variant?.sku ?? "",
    name: variant?.name ?? "",
    price: variant?.price ?? "",
    cost: variant?.cost ?? "",
    on_hand: String(variant?.on_hand ?? 0),
    is_active: variant?.is_active ?? true,
    packaged_weight_grams: String(variant?.packaged_weight_grams ?? 1),
    length_cm: variant?.length_cm ?? "1",
    width_cm: variant?.width_cm ?? "1",
    height_cm: variant?.height_cm ?? "1",
    attribute_values: Object.fromEntries(
      (variant?.attributes ?? []).map((attribute) => [
        attribute.definition_id,
        String(attribute.value),
      ]),
    ),
  };
}

function accessibleLabel(label: string, index: number) {
  return index === 0 ? undefined : `${label} de variante ${index + 1}`;
}

export function ManagementProductEditor({
  categories,
  brands,
  attributes = [],
  initial,
  onSave,
}: {
  categories: ManagementCategory[];
  brands: ManagementBrand[];
  attributes?: ManagementAttributeDefinition[];
  initial?: ManagementProduct;
  onSave: (payload: ProductEditorPayload) => Promise<ManagementProduct>;
}) {
  const [variants, setVariants] = useState<VariantDraft[]>(
    initial?.variants.length
      ? initial.variants.map((variant) => draftFromVariant(variant))
      : [draftFromVariant()],
  );
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const updateVariant = <K extends keyof VariantDraft>(
    index: number,
    field: K,
    value: VariantDraft[K],
  ) => setVariants((rows) => rows.map((row, rowIndex) => (
    rowIndex === index ? { ...row, [field]: value } : row
  )));

  const updateAttribute = (index: number, definitionId: number, value: string) => {
    setVariants((rows) => rows.map((row, rowIndex) => rowIndex === index ? {
      ...row,
      attribute_values: { ...row.attribute_values, [definitionId]: value },
    } : row));
  };

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
      variants: variants.map((variant) => ({
        ...(variant.id ? { id: variant.id } : {}),
        sku: variant.sku,
        name: variant.name,
        price: variant.price,
        cost: variant.cost,
        on_hand: Number(variant.on_hand),
        is_active: variant.is_active,
        packaged_weight_grams: Number(variant.packaged_weight_grams),
        length_cm: variant.length_cm,
        width_cm: variant.width_cm,
        height_cm: variant.height_cm,
        attribute_values: attributes.flatMap((definition) => {
          const raw = variant.attribute_values[definition.id];
          if (raw === undefined || raw === "") return [];
          const value = definition.value_type === "boolean" ? raw === "true" : raw;
          return [{ definition_id: definition.id, value }];
        }),
      })),
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
        <div className="management-section-heading">
          <div><h2>Variantes</h2><p>Agregá colores, tamaños o presentaciones con su propio precio, costo, stock y medidas.</p></div>
          <button className="button secondary" onClick={() => setVariants((rows) => [...rows, draftFromVariant(undefined, `new-${rows.length + 1}-${Date.now()}`)])} type="button">Agregar variante</button>
        </div>
        <div className="management-variant-list">
          {variants.map((variant, index) => (
            <fieldset className="management-variant-card" key={variant.key}>
              <legend>Variante {index + 1}</legend>
              <div className="management-field-grid">
                <label><span>SKU</span><input aria-label={accessibleLabel("SKU", index)} onChange={(event) => updateVariant(index, "sku", event.target.value)} required value={variant.sku} /></label>
                <label><span>Nombre de la variante</span><input aria-label={accessibleLabel("Nombre de la variante", index)} onChange={(event) => updateVariant(index, "name", event.target.value)} placeholder="Ej.: Azul, A4 o Pack x6" value={variant.name} /></label>
                <label><span>Precio</span><input aria-label={accessibleLabel("Precio", index)} min="0" onChange={(event) => updateVariant(index, "price", event.target.value)} required step="0.01" type="number" value={variant.price} /></label>
                <label><span>Costo</span><input aria-label={accessibleLabel("Costo", index)} min="0" onChange={(event) => updateVariant(index, "cost", event.target.value)} required step="0.01" type="number" value={variant.cost} /></label>
                <label><span>Stock físico</span><input aria-label={accessibleLabel("Stock físico", index)} min="0" onChange={(event) => updateVariant(index, "on_hand", event.target.value)} type="number" value={variant.on_hand} /></label>
                <label><span>Peso embalado (gramos)</span><input aria-label={accessibleLabel("Peso embalado (gramos)", index)} min="1" onChange={(event) => updateVariant(index, "packaged_weight_grams", event.target.value)} type="number" value={variant.packaged_weight_grams} /></label>
                <label><span>Largo (cm)</span><input aria-label={accessibleLabel("Largo (cm)", index)} min="0.01" onChange={(event) => updateVariant(index, "length_cm", event.target.value)} step="0.01" type="number" value={variant.length_cm} /></label>
                <label><span>Ancho (cm)</span><input aria-label={accessibleLabel("Ancho (cm)", index)} min="0.01" onChange={(event) => updateVariant(index, "width_cm", event.target.value)} step="0.01" type="number" value={variant.width_cm} /></label>
                <label><span>Alto (cm)</span><input aria-label={accessibleLabel("Alto (cm)", index)} min="0.01" onChange={(event) => updateVariant(index, "height_cm", event.target.value)} step="0.01" type="number" value={variant.height_cm} /></label>
                {attributes.map((definition) => (
                  <label key={definition.id}>
                    <span>{definition.name}</span>
                    {definition.value_type === "option" ? (
                      <select aria-label={accessibleLabel(definition.name, index)} onChange={(event) => updateAttribute(index, definition.id, event.target.value)} value={variant.attribute_values[definition.id] ?? ""}>
                        <option value="">Sin especificar</option>
                        {definition.options.map((option) => <option key={option.id} value={option.value}>{option.label}</option>)}
                      </select>
                    ) : definition.value_type === "boolean" ? (
                      <select aria-label={accessibleLabel(definition.name, index)} onChange={(event) => updateAttribute(index, definition.id, event.target.value)} value={variant.attribute_values[definition.id] ?? ""}>
                        <option value="">Sin especificar</option><option value="true">Sí</option><option value="false">No</option>
                      </select>
                    ) : (
                      <input aria-label={accessibleLabel(definition.name, index)} onChange={(event) => updateAttribute(index, definition.id, event.target.value)} step={definition.value_type === "decimal" ? "0.01" : undefined} type={["integer", "decimal"].includes(definition.value_type) ? "number" : "text"} value={variant.attribute_values[definition.id] ?? ""} />
                    )}
                  </label>
                ))}
                <label className="management-check field-wide"><input checked={variant.is_active} onChange={(event) => updateVariant(index, "is_active", event.target.checked)} type="checkbox" /><span>Variante activa</span></label>
              </div>
              {!variant.id && variants.length > 1 && <button className="button text" onClick={() => setVariants((rows) => rows.filter((_, rowIndex) => rowIndex !== index))} type="button">Quitar variante</button>}
            </fieldset>
          ))}
        </div>
      </section>
      {state === "saved" && <p className="success-message">Producto guardado.</p>}
      {state === "error" && <p className="inline-error">No pudimos guardar el producto. Revisá los campos.</p>}
      <button className="button primary" disabled={state === "saving" || !categories.length} type="submit">{state === "saving" ? "Guardando…" : "Guardar producto"}</button>
    </form>
  );
}
