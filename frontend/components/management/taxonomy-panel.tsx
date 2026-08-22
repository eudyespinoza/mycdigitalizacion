"use client";

import { FormEvent, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { managementRequest } from "@/lib/management/api";
import type {
  ManagementAttributeDefinition,
  ManagementBrand,
  ManagementCategory,
} from "@/lib/management/catalog-types";


export function TaxonomyPanel({ initialCategories, initialBrands, initialAttributes }: { initialCategories: ManagementCategory[]; initialBrands: ManagementBrand[]; initialAttributes: ManagementAttributeDefinition[] }) {
  const [categories, setCategories] = useState(initialCategories);
  const [brands, setBrands] = useState(initialBrands);
  const [attributes, setAttributes] = useState(initialAttributes);
  const [activeForm, setActiveForm] = useState<"category" | "brand" | "attribute" | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const normalizedSlug = (name: string) => name.toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const createCategory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("name"));
    setSaving(true);
    setError("");
    try {
      const created = await managementRequest<ManagementCategory>("/categories/", {
        method: "POST",
        body: JSON.stringify({ name, slug: normalizedSlug(name), parent_id: form.get("parent_id") ? Number(form.get("parent_id")) : null, is_active: true }),
      });
      setCategories((rows) => [...rows, created]);
      setActiveForm(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos guardar la categoría.");
    } finally {
      setSaving(false);
    }
  };
  const createBrand = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("name"));
    setSaving(true);
    setError("");
    try {
      const created = await managementRequest<ManagementBrand>("/brands/", {
        method: "POST",
        body: JSON.stringify({ name, slug: normalizedSlug(name) }),
      });
      setBrands((rows) => [...rows, created]);
      setActiveForm(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos guardar la marca.");
    } finally {
      setSaving(false);
    }
  };
  const createAttribute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("attribute_name"));
    const valueType = String(form.get("value_type"));
    const optionLabels = String(form.get("options") ?? "").split(",").map((item) => item.trim()).filter(Boolean);
    setSaving(true);
    setError("");
    try {
      const created = await managementRequest<ManagementAttributeDefinition>("/attributes/", {
        method: "POST",
        body: JSON.stringify({
          name,
          slug: normalizedSlug(name),
          value_type: valueType,
          is_filterable: form.has("is_filterable"),
          options: valueType === "option" ? optionLabels.map((label) => ({ label, value: normalizedSlug(label) })) : [],
        }),
      });
      setAttributes((rows) => [...rows, created]);
      setActiveForm(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos guardar el atributo.");
    } finally {
      setSaving(false);
    }
  };
  const openForm = (form: "category" | "brand" | "attribute") => {
    setError("");
    setActiveForm(form);
  };
  return (
    <div className="taxonomy-grid">
      <section className="management-form-section">
        <div className="management-section-heading">
          <div><h2>Categorías</h2><p>Jerarquía principal del catálogo.</p></div>
          <button className="button primary" onClick={() => openForm("category")} type="button">Nueva categoría</button>
        </div>
        {categories.length ? <ul className="management-simple-list">{categories.map((category) => <li key={category.id}><strong>{category.name}</strong><span>{category.parent_id ? "Subcategoría" : "Principal"}</span></li>)}</ul> : <p>Todavía no cargaste categorías.</p>}
      </section>
      <section className="management-form-section">
        <div className="management-section-heading">
          <div><h2>Marcas</h2><p>Fabricantes o líneas comerciales.</p></div>
          <button className="button primary" onClick={() => openForm("brand")} type="button">Nueva marca</button>
        </div>
        {brands.length ? <ul className="management-simple-list">{brands.map((brand) => <li key={brand.id}><strong>{brand.name}</strong><span>{brand.slug}</span></li>)}</ul> : <p>Todavía no cargaste marcas.</p>}
      </section>
      <section className="management-form-section taxonomy-attributes">
        <div className="management-section-heading">
          <div><h2>Atributos y filtros</h2><p>Color, tamaño, material y otros datos de variantes.</p></div>
          <button className="button primary" onClick={() => openForm("attribute")} type="button">Nuevo atributo</button>
        </div>
        {attributes.length ? <ul className="management-simple-list">{attributes.map((attribute) => <li key={attribute.id}><div><strong>{attribute.name}</strong><span>{attribute.options.map((option) => option.label).join(", ") || attribute.value_type}</span></div><span>{attribute.is_filterable ? "Filtro visible" : "Dato interno"}</span></li>)}</ul> : <p>Todavía no cargaste atributos.</p>}
      </section>
      <ManagementFormDialog onClose={() => { if (!saving) setActiveForm(null); }} open={activeForm === "category"} title="Nueva categoría">
        <form className="compact-management-form" onSubmit={(event) => void createCategory(event)}>
          <label><span>Nombre de la categoría</span><input name="name" required /></label>
          <label><span>Categoría superior</span><select name="parent_id"><option value="">Ninguna</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar categoría"}</button><button className="button secondary" disabled={saving} onClick={() => setActiveForm(null)} type="button">Cancelar</button></div>
        </form>
      </ManagementFormDialog>
      <ManagementFormDialog onClose={() => { if (!saving) setActiveForm(null); }} open={activeForm === "brand"} title="Nueva marca">
        <form className="compact-management-form" onSubmit={(event) => void createBrand(event)}>
          <label><span>Nombre de la marca</span><input name="name" required /></label>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar marca"}</button><button className="button secondary" disabled={saving} onClick={() => setActiveForm(null)} type="button">Cancelar</button></div>
        </form>
      </ManagementFormDialog>
      <ManagementFormDialog onClose={() => { if (!saving) setActiveForm(null); }} open={activeForm === "attribute"} size="wide" title="Nuevo atributo">
        <form className="compact-management-form" onSubmit={(event) => void createAttribute(event)}>
          <div className="management-field-grid">
            <label><span>Nombre del atributo</span><input name="attribute_name" placeholder="Ej.: Color" required /></label>
            <label><span>Tipo de valor</span><select name="value_type"><option value="option">Lista de opciones</option><option value="text">Texto</option><option value="integer">Número entero</option><option value="decimal">Número decimal</option><option value="boolean">Sí o no</option></select></label>
            <label className="field-wide"><span>Opciones separadas por coma</span><input name="options" placeholder="Azul, Rosa, Negro" /></label>
            <label className="management-check field-wide"><input defaultChecked name="is_filterable" type="checkbox" /><span>Mostrar como filtro del catálogo</span></label>
          </div>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar atributo"}</button><button className="button secondary" disabled={saving} onClick={() => setActiveForm(null)} type="button">Cancelar</button></div>
        </form>
      </ManagementFormDialog>
    </div>
  );
}
