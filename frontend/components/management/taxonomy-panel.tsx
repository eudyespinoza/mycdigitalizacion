"use client";

import { FormEvent, useState } from "react";

import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { managementRequest } from "@/lib/management/api";
import type {
  ManagementAttributeDefinition,
  ManagementBrand,
  ManagementCategory,
} from "@/lib/management/catalog-types";

type EditorState =
  | { kind: "category"; item?: ManagementCategory }
  | { kind: "brand"; item?: ManagementBrand }
  | { kind: "attribute"; item?: ManagementAttributeDefinition };

type DeleteTarget =
  | { kind: "category"; item: ManagementCategory }
  | { kind: "brand"; item: ManagementBrand }
  | { kind: "attribute"; item: ManagementAttributeDefinition };

const deleteLabels = {
  category: "categoría",
  brand: "marca",
  attribute: "atributo",
} as const;

const deletePaths = {
  category: "categories",
  brand: "brands",
  attribute: "attributes",
} as const;

function normalizedSlug(name: string) {
  return name.toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function replaceOrAppend<T extends { id: number }>(rows: T[], saved: T, editing: boolean) {
  return editing ? rows.map((row) => row.id === saved.id ? saved : row) : [...rows, saved];
}

export function TaxonomyPanel({
  initialCategories,
  initialBrands,
  initialAttributes,
}: {
  initialCategories: ManagementCategory[];
  initialBrands: ManagementBrand[];
  initialAttributes: ManagementAttributeDefinition[];
}) {
  const [categories, setCategories] = useState(initialCategories);
  const [brands, setBrands] = useState(initialBrands);
  const [attributes, setAttributes] = useState(initialAttributes);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DeleteTarget | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const closeDialogs = () => {
    if (saving) return;
    setEditor(null);
    setPendingDelete(null);
    setError("");
  };

  const openCreate = (kind: EditorState["kind"]) => {
    setError("");
    setEditor({ kind });
  };

  const submitCategory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editor?.kind !== "category") return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const editing = editor.item;
    setSaving(true);
    setError("");
    try {
      const saved = await managementRequest<ManagementCategory>(
        editing ? `/categories/${editing.id}/` : "/categories/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({
            name,
            slug: normalizedSlug(name),
            parent_id: form.get("parent_id") ? Number(form.get("parent_id")) : null,
            is_active: form.has("is_active"),
          }),
        },
      );
      setCategories((rows) => replaceOrAppend(rows, saved, Boolean(editing)));
      setEditor(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos guardar la categoría.");
    } finally {
      setSaving(false);
    }
  };

  const submitBrand = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editor?.kind !== "brand") return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const editing = editor.item;
    setSaving(true);
    setError("");
    try {
      const saved = await managementRequest<ManagementBrand>(
        editing ? `/brands/${editing.id}/` : "/brands/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({ name, slug: normalizedSlug(name) }),
        },
      );
      setBrands((rows) => replaceOrAppend(rows, saved, Boolean(editing)));
      setEditor(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos guardar la marca.");
    } finally {
      setSaving(false);
    }
  };

  const submitAttribute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editor?.kind !== "attribute") return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("attribute_name") ?? "").trim();
    const valueType = String(form.get("value_type")) as ManagementAttributeDefinition["value_type"];
    const optionLabels = String(form.get("options") ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const editing = editor.item;
    setSaving(true);
    setError("");
    try {
      const saved = await managementRequest<ManagementAttributeDefinition>(
        editing ? `/attributes/${editing.id}/` : "/attributes/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({
            name,
            slug: normalizedSlug(name),
            value_type: valueType,
            is_filterable: form.has("is_filterable"),
            options: valueType === "option" ? optionLabels.map((label, index) => ({
              ...(editing?.options[index]?.id ? { id: editing.options[index].id } : {}),
              label,
              value: normalizedSlug(label),
            })) : [],
          }),
        },
      );
      setAttributes((rows) => replaceOrAppend(rows, saved, Boolean(editing)));
      setEditor(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos guardar el atributo.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!pendingDelete) return;
    setSaving(true);
    setError("");
    try {
      await managementRequest<void>(
        `/${deletePaths[pendingDelete.kind]}/${pendingDelete.item.id}/`,
        { method: "DELETE" },
      );
      if (pendingDelete.kind === "category") {
        setCategories((rows) => rows.filter((row) => row.id !== pendingDelete.item.id));
      } else if (pendingDelete.kind === "brand") {
        setBrands((rows) => rows.filter((row) => row.id !== pendingDelete.item.id));
      } else {
        setAttributes((rows) => rows.filter((row) => row.id !== pendingDelete.item.id));
      }
      setPendingDelete(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos eliminar el registro.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="taxonomy-grid">
      <section className="management-form-section">
        <div className="management-section-heading">
          <div><h2>Categorías</h2><p>Jerarquía principal del catálogo.</p></div>
          <button className="button primary" onClick={() => openCreate("category")} type="button">Nueva categoría</button>
        </div>
        {categories.length ? <ul className="management-simple-list taxonomy-list">{categories.map((category) => {
          const parent = categories.find((candidate) => candidate.id === category.parent_id);
          return <li key={category.id}>
            <div className="taxonomy-row-main"><strong>{category.name}</strong><span>{parent ? `Subcategoría de ${parent.name}` : "Principal"} · {category.is_active ? "Habilitada" : "Deshabilitada"}</span></div>
            <div className="management-content-actions taxonomy-row-actions">
              <button aria-label={`Editar ${category.name}`} className="text-button" onClick={() => { setError(""); setEditor({ kind: "category", item: category }); }} type="button">Editar</button>
              <button aria-label={`Eliminar ${category.name}`} className="text-button danger" onClick={() => { setError(""); setPendingDelete({ kind: "category", item: category }); }} type="button">Eliminar</button>
            </div>
          </li>;
        })}</ul> : <p>Todavía no cargaste categorías.</p>}
      </section>

      <section className="management-form-section">
        <div className="management-section-heading">
          <div><h2>Marcas</h2><p>Fabricantes o líneas comerciales.</p></div>
          <button className="button primary" onClick={() => openCreate("brand")} type="button">Nueva marca</button>
        </div>
        {brands.length ? <ul className="management-simple-list taxonomy-list">{brands.map((brand) => <li key={brand.id}>
          <div className="taxonomy-row-main"><strong>{brand.name}</strong><span>{brand.slug}</span></div>
          <div className="management-content-actions taxonomy-row-actions">
            <button aria-label={`Editar ${brand.name}`} className="text-button" onClick={() => { setError(""); setEditor({ kind: "brand", item: brand }); }} type="button">Editar</button>
            <button aria-label={`Eliminar ${brand.name}`} className="text-button danger" onClick={() => { setError(""); setPendingDelete({ kind: "brand", item: brand }); }} type="button">Eliminar</button>
          </div>
        </li>)}</ul> : <p>Todavía no cargaste marcas.</p>}
      </section>

      <section className="management-form-section taxonomy-attributes">
        <div className="management-section-heading">
          <div><h2>Atributos y filtros</h2><p>Color, tamaño, material y otros datos de variantes.</p></div>
          <button className="button primary" onClick={() => openCreate("attribute")} type="button">Nuevo atributo</button>
        </div>
        {attributes.length ? <ul className="management-simple-list taxonomy-list">{attributes.map((attribute) => <li key={attribute.id}>
          <div className="taxonomy-row-main"><strong>{attribute.name}</strong><span>{attribute.options.map((option) => option.label).join(", ") || attribute.value_type} · {attribute.is_filterable ? "Filtro visible" : "Dato interno"}</span></div>
          <div className="management-content-actions taxonomy-row-actions">
            <button aria-label={`Editar ${attribute.name}`} className="text-button" onClick={() => { setError(""); setEditor({ kind: "attribute", item: attribute }); }} type="button">Editar</button>
            <button aria-label={`Eliminar ${attribute.name}`} className="text-button danger" onClick={() => { setError(""); setPendingDelete({ kind: "attribute", item: attribute }); }} type="button">Eliminar</button>
          </div>
        </li>)}</ul> : <p>Todavía no cargaste atributos.</p>}
      </section>

      <ManagementFormDialog onClose={closeDialogs} open={editor?.kind === "category"} title={editor?.kind === "category" && editor.item ? "Editar categoría" : "Nueva categoría"}>
        {editor?.kind === "category" ? <form className="compact-management-form" onSubmit={(event) => void submitCategory(event)}>
          <label><span>Nombre de la categoría</span><input defaultValue={editor.item?.name ?? ""} name="name" required /></label>
          <label><span>Categoría superior</span><select defaultValue={editor.item?.parent_id ?? ""} name="parent_id"><option value="">Ninguna</option>{categories.filter((category) => category.id !== editor.item?.id).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label className="management-check"><input defaultChecked={editor.item?.is_active ?? true} name="is_active" type="checkbox" /><span>Habilitada</span></label>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : editor.item ? "Guardar cambios" : "Guardar categoría"}</button><button className="button secondary" disabled={saving} onClick={closeDialogs} type="button">Cancelar</button></div>
        </form> : null}
      </ManagementFormDialog>

      <ManagementFormDialog onClose={closeDialogs} open={editor?.kind === "brand"} title={editor?.kind === "brand" && editor.item ? "Editar marca" : "Nueva marca"}>
        {editor?.kind === "brand" ? <form className="compact-management-form" onSubmit={(event) => void submitBrand(event)}>
          <label><span>Nombre de la marca</span><input defaultValue={editor.item?.name ?? ""} name="name" required /></label>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : editor.item ? "Guardar cambios" : "Guardar marca"}</button><button className="button secondary" disabled={saving} onClick={closeDialogs} type="button">Cancelar</button></div>
        </form> : null}
      </ManagementFormDialog>

      <ManagementFormDialog onClose={closeDialogs} open={editor?.kind === "attribute"} size="wide" title={editor?.kind === "attribute" && editor.item ? "Editar atributo" : "Nuevo atributo"}>
        {editor?.kind === "attribute" ? <form className="compact-management-form" onSubmit={(event) => void submitAttribute(event)}>
          <div className="management-field-grid">
            <label><span>Nombre del atributo</span><input defaultValue={editor.item?.name ?? ""} name="attribute_name" placeholder="Ej.: Color" required /></label>
            <label><span>Tipo de valor</span><select defaultValue={editor.item?.value_type ?? "option"} name="value_type"><option value="option">Lista de opciones</option><option value="text">Texto</option><option value="integer">Número entero</option><option value="decimal">Número decimal</option><option value="boolean">Sí o no</option></select></label>
            <label className="field-wide"><span>Opciones separadas por coma</span><input defaultValue={editor.item?.options.map((option) => option.label).join(", ") ?? ""} name="options" placeholder="Azul, Rosa, Negro" /></label>
            <label className="management-check field-wide"><input defaultChecked={editor.item?.is_filterable ?? true} name="is_filterable" type="checkbox" /><span>Mostrar como filtro del catálogo</span></label>
          </div>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : editor.item ? "Guardar cambios" : "Guardar atributo"}</button><button className="button secondary" disabled={saving} onClick={closeDialogs} type="button">Cancelar</button></div>
        </form> : null}
      </ManagementFormDialog>

      <ConfirmationDialog
        busy={saving}
        busyLabel="Eliminando…"
        confirmLabel="Sí, eliminar"
        description={pendingDelete ? `“${pendingDelete.item.name}” se eliminará definitivamente. Si está en uso, el sistema conservará el registro y te lo informará.` : ""}
        error={error}
        onCancel={closeDialogs}
        onConfirm={remove}
        open={Boolean(pendingDelete)}
        title={pendingDelete ? `Eliminar ${deleteLabels[pendingDelete.kind]}` : "Eliminar registro"}
      />
    </div>
  );
}
