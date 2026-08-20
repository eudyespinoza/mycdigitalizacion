"use client";

import { FormEvent, useState } from "react";

import type { ManagementRole } from "@/lib/management/access-types";


export function ManagementUserEditor({ roles, onSave }: { roles: ManagementRole[]; onSave: (payload: Record<string, unknown>) => Promise<void> }) {
  const [state, setState] = useState("idle");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      email: String(form.get("email")),
      first_name: String(form.get("first_name") ?? ""),
      last_name: String(form.get("last_name") ?? ""),
      password: String(form.get("password")),
      role_names: roles.filter((role) => form.has(`role_${role.name}`)).map((role) => role.name),
      is_active: true,
    };
    setState("saving");
    try { await onSave(payload); event.currentTarget.reset(); setState("saved"); } catch { setState("error"); }
  };
  return <form className="management-form-section compact-management-form" onSubmit={(event) => void submit(event)}><div><p className="management-kicker">Acceso interno</p><h2>Nuevo usuario</h2><p>Las cuentas del equipo quedan verificadas al crearlas.</p></div><label><span>Email</span><input name="email" required type="email" /></label><div className="management-field-grid"><label><span>Nombre</span><input name="first_name" /></label><label><span>Apellido</span><input name="last_name" /></label></div><label><span>Contraseña temporal</span><input minLength={12} name="password" required type="password" /></label><fieldset className="management-role-list"><legend>Roles</legend>{roles.map((role) => <label className="management-check" key={role.name}><input aria-label={role.label} name={`role_${role.name}`} type="checkbox" /><span><strong>{role.label}</strong><small>{role.permission_count} permisos limitados</small></span></label>)}</fieldset><button className="button primary" disabled={state === "saving"} type="submit">Crear usuario</button>{state === "saved" && <p className="success-message">Usuario creado.</p>}{state === "error" && <p className="inline-error">No pudimos crear el usuario.</p>}</form>;
}
