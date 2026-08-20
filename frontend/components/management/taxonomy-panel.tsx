"use client";

import { FormEvent, useState } from "react";

import { managementRequest } from "@/lib/management/api";
import type { ManagementBrand, ManagementCategory } from "@/lib/management/catalog-types";


export function TaxonomyPanel({ initialCategories, initialBrands }: { initialCategories: ManagementCategory[]; initialBrands: ManagementBrand[] }) {
  const [categories, setCategories] = useState(initialCategories);
  const [brands, setBrands] = useState(initialBrands);
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
  return <div className="taxonomy-grid"><section className="management-form-section"><h2>Categorías</h2><form className="compact-management-form" onSubmit={(event) => void createCategory(event)}><label><span>Nombre</span><input name="name" required /></label><label><span>Categoría superior</span><select name="parent_id"><option value="">Ninguna</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><button className="button primary" type="submit">Agregar categoría</button></form><ul className="management-simple-list">{categories.map((category) => <li key={category.id}><strong>{category.name}</strong><span>{category.parent_id ? "Subcategoría" : "Principal"}</span></li>)}</ul></section><section className="management-form-section"><h2>Marcas</h2><form className="compact-management-form" onSubmit={(event) => void createBrand(event)}><label><span>Nombre</span><input name="name" required /></label><button className="button primary" type="submit">Agregar marca</button></form><ul className="management-simple-list">{brands.map((brand) => <li key={brand.id}><strong>{brand.name}</strong><span>{brand.slug}</span></li>)}</ul></section></div>;
}
