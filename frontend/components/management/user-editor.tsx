"use client";

import { FormEvent, useState } from "react";

import type { ManagementRole, ManagementStaffUser } from "@/lib/management/access-types";


type ManagementUserEditorProps = {
  initialValue?: ManagementStaffUser;
  onCancel?: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  roles: ManagementRole[];
};


export function ManagementUserEditor({ initialValue, onCancel, onSave, roles }: ManagementUserEditorProps) {
  const [state, setState] = useState("idle");
  const editing = Boolean(initialValue);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const payload = {
      email: String(form.get("email")),
      first_name: String(form.get("first_name") ?? ""),
      last_name: String(form.get("last_name") ?? ""),
      role_names: roles.filter((role) => form.has(`role_${role.name}`)).map((role) => role.name),
      is_active: initialValue?.is_active ?? true,
      ...(password ? { password } : {}),
    };
    setState("saving");
    try { await onSave(payload); setState("saved"); } catch { setState("error"); }
  };
  return (
    <form className="compact-management-form management-user-editor" onSubmit={(event) => void submit(event)}>
      <p>Las cuentas internas quedan verificadas al crearlas. Los permisos se asignan mediante roles.</p>
      <label><span>Email</span><input defaultValue={initialValue?.email ?? ""} name="email" required type="email" /></label>
      <div className="management-field-grid">
        <label><span>Nombre</span><input defaultValue={initialValue?.first_name ?? ""} name="first_name" /></label>
        <label><span>Apellido</span><input defaultValue={initialValue?.last_name ?? ""} name="last_name" /></label>
      </div>
      <label>
        <span>{editing ? "Nueva contraseña (opcional)" : "Contraseña temporal"}</span>
        <input minLength={12} name="password" required={!editing} type="password" />
      </label>
      <fieldset className="management-role-list">
        <legend>Roles y permisos</legend>
        {roles.map((role) => (
          <label className="management-check" key={role.name}>
            <input
              aria-label={role.label}
              defaultChecked={initialValue?.role_names.includes(role.name) ?? false}
              name={`role_${role.name}`}
              type="checkbox"
            />
            <span><strong>{role.label}</strong><small>{role.permission_count} permisos limitados</small></span>
          </label>
        ))}
      </fieldset>
      {state === "error" ? <p className="inline-error" role="alert">No pudimos guardar el usuario. Revisá los datos e intentá nuevamente.</p> : null}
      <div className="management-form-actions">
        <button className="button primary" disabled={state === "saving"} type="submit">
          {state === "saving" ? "Guardando…" : editing ? "Guardar cambios" : "Crear usuario"}
        </button>
        {onCancel ? <button className="button secondary" onClick={onCancel} type="button">Cancelar</button> : null}
      </div>
    </form>
  );
}
