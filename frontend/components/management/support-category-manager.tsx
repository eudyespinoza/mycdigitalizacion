"use client";

import { FormEvent, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { managementRequest } from "@/lib/management/api";
import type { ManagementSupportCategory } from "@/lib/management/support-types";

type EditorState = { mode: "create" } | { mode: "edit"; category: ManagementSupportCategory };

const kindLabels = { consultation: "Consultas", problem: "Reportar un problema" } as const;

function sortCategories(categories: ManagementSupportCategory[]) {
  return [...categories].sort((left, right) =>
    left.kind.localeCompare(right.kind) || left.sort_order - right.sort_order || left.id - right.id,
  );
}

export function SupportCategoryManager({ initialCategories }: { initialCategories: ManagementSupportCategory[] }) {
  const [categories, setCategories] = useState(() => sortCategories(initialCategories));
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ManagementSupportCategory | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const closeDialogs = () => {
    if (saving) return;
    setEditor(null);
    setPendingDelete(null);
    setError("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editor) return;
    const form = new FormData(event.currentTarget);
    const payload = {
      kind: editor.mode === "edit" ? editor.category.kind : String(form.get("kind")),
      label: String(form.get("label") ?? "").trim(),
      sort_order: Number(form.get("sort_order") ?? 0),
      is_active: form.has("is_active"),
    };
    setSaving(true);
    setError("");
    try {
      const editing = editor.mode === "edit" ? editor.category : null;
      const saved = await managementRequest<ManagementSupportCategory>(
        editing ? `/support/categories/${editing.id}/` : "/support/categories/",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) },
      );
      setCategories((current) => sortCategories(editing
        ? current.map((category) => category.id === saved.id ? saved : category)
        : [...current, saved]));
      setEditor(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos guardar la categoría.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!pendingDelete) return;
    setSaving(true);
    setError("");
    try {
      await managementRequest<void>(`/support/categories/${pendingDelete.id}/`, { method: "DELETE" });
      setCategories((current) => current.filter((category) => category.id !== pendingDelete.id));
      setPendingDelete(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos eliminar la categoría.");
    } finally {
      setSaving(false);
    }
  };

  return <section aria-labelledby="support-category-title" className="management-list-section support-category-manager">
    <header className="management-section-heading">
      <div><h1 id="support-category-title">Categorías de atención</h1><p>Definí las opciones que aparecen al crear una consulta o reportar un problema.</p></div>
      <button className="button primary" onClick={() => { setError(""); setEditor({ mode: "create" }); }} type="button">Nueva categoría</button>
    </header>

    <div className="support-category-groups">
      {(["consultation", "problem"] as const).map((kind) => {
        const rows = categories.filter((category) => category.kind === kind);
        return <section className="management-form-section" key={kind}>
          <div className="management-section-heading"><div><h2>{kindLabels[kind]}</h2><p>{rows.length} {rows.length === 1 ? "categoría" : "categorías"}</p></div></div>
          {rows.length ? <ul className="support-category-list">{rows.map((category) => <li key={category.id}>
            <div><strong>{category.label}</strong><span>{category.is_active ? "Visible" : "Deshabilitada"} · orden {category.sort_order}</span></div>
            <div className="management-content-actions">
              <button aria-label={`Editar ${category.label}`} className="text-button" onClick={() => { setError(""); setEditor({ mode: "edit", category }); }} type="button">Editar</button>
              <button aria-label={`Eliminar ${category.label}`} className="text-button danger" onClick={() => { setError(""); setPendingDelete(category); }} type="button">Eliminar</button>
            </div>
          </li>)}</ul> : <p className="management-empty">No hay categorías cargadas para esta opción.</p>}
        </section>;
      })}
    </div>

    <ManagementFormDialog description="El nombre será visible para los clientes. El identificador web se genera automáticamente al crearla." onClose={closeDialogs} open={Boolean(editor)} title={editor?.mode === "edit" ? "Editar categoría" : "Nueva categoría"}>
      {editor ? <form className="compact-management-form" onSubmit={(event) => void submit(event)}>
        <label><span>Tipo de atención</span><select defaultValue={editor.mode === "edit" ? editor.category.kind : "consultation"} disabled={editor.mode === "edit"} name="kind"><option value="consultation">Consulta</option><option value="problem">Reportar un problema</option></select></label>
        <label><span>Nombre</span><input defaultValue={editor.mode === "edit" ? editor.category.label : ""} maxLength={80} name="label" required /></label>
        <label><span>Orden</span><input defaultValue={editor.mode === "edit" ? editor.category.sort_order : 10} min={0} name="sort_order" type="number" /></label>
        <label className="management-check"><input defaultChecked={editor.mode === "create" || editor.category.is_active} name="is_active" type="checkbox" /><span>Habilitada</span></label>
        {error ? <p className="inline-error" role="alert">{error}</p> : null}
        <div className="management-form-actions"><button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : editor.mode === "edit" ? "Guardar cambios" : "Guardar categoría"}</button><button className="button secondary" disabled={saving} onClick={closeDialogs} type="button">Cancelar</button></div>
      </form> : null}
    </ManagementFormDialog>

    <ManagementFormDialog description={pendingDelete ? `“${pendingDelete.label}” dejará de aparecer en nuevos casos. Los casos anteriores conservarán su categoría.` : undefined} onClose={closeDialogs} open={Boolean(pendingDelete)} title="Eliminar categoría">
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <div className="management-form-actions"><button className="button destructive" disabled={saving} onClick={() => void remove()} type="button">{saving ? "Eliminando…" : "Sí, eliminar"}</button><button className="button secondary" disabled={saving} onClick={closeDialogs} type="button">Cancelar</button></div>
    </ManagementFormDialog>
  </section>;
}
