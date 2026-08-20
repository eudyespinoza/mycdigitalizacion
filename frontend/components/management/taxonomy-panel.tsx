"use client";

import { FormEvent, useState } from "react";

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
  const normalizedSlug = (name: string) => name.toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const createCategory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("name"));
    const created = await managementRequest<ManagementCategory>("/categories/", {
      method: "POST",
      body: JSON.stringify({ name, slug: normalizedSlug(name), parent_id: form.get("parent_id") ? Number(form.get("parent_id")) : null, is_active: true }),
    });
    setCategories((rows) => [...rows, created]);
    element.reset();
  };
  const createBrand = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("name"));
    const created = await managementRequest<ManagementBrand>("/brands/", {
      method: "POST",
      body: JSON.stringify({ name, slug: normalizedSlug(name) }),
    });
    setBrands((rows) => [...rows, created]);
    element.reset();
  };
  const createAttribute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const name = String(form.get("attribute_name"));
    const valueType = String(form.get("value_type"));
    const optionLabels = String(form.get("options") ?? "").split(",").map((item) => item.trim()).filter(Boolean);
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
    element.reset();
  };
  return <div className="taxonomy-grid"><section className="management-form-section"><h2>Categorías</h2><form className="compact-management-form" onSubmit={(event) => void createCategory(event)}><label><span>Nombre</span><input name="name" required /></label><label><span>Categoría superior</span><select name="parent_id"><option value="">Ninguna</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><button className="button primary" type="submit">Agregar categoría</button></form><ul className="management-simple-list">{categories.map((category) => <li key={category.id}><strong>{category.name}</strong><span>{category.parent_id ? "Subcategoría" : "Principal"}</span></li>)}</ul></section><section className="management-form-section"><h2>Marcas</h2><form className="compact-management-form" onSubmit={(event) => void createBrand(event)}><label><span>Nombre</span><input name="name" required /></label><button className="button primary" type="submit">Agregar marca</button></form><ul className="management-simple-list">{brands.map((brand) => <li key={brand.id}><strong>{brand.name}</strong><span>{brand.slug}</span></li>)}</ul></section><section className="management-form-section taxonomy-attributes"><h2>Atributos y filtros</h2><p>Definí color, tamaño, material u otros datos que después aparecen en cada variante.</p><form className="compact-management-form" onSubmit={(event) => void createAttribute(event)}><label><span>Nombre del atributo</span><input name="attribute_name" placeholder="Ej.: Color" required /></label><label><span>Tipo de valor</span><select name="value_type"><option value="option">Lista de opciones</option><option value="text">Texto</option><option value="integer">Número entero</option><option value="decimal">Número decimal</option><option value="boolean">Sí o no</option></select></label><label><span>Opciones separadas por coma</span><input name="options" placeholder="Azul, Rosa, Negro" /></label><label className="management-check"><input defaultChecked name="is_filterable" type="checkbox" /><span>Mostrar como filtro del catálogo</span></label><button className="button primary" type="submit">Agregar atributo</button></form><ul className="management-simple-list">{attributes.map((attribute) => <li key={attribute.id}><div><strong>{attribute.name}</strong><span>{attribute.options.map((option) => option.label).join(", ") || attribute.value_type}</span></div><span>{attribute.is_filterable ? "Filtro visible" : "Dato interno"}</span></li>)}</ul></section></div>;
}
