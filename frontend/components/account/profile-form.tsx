"use client";

import { useRef, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import type { Customer } from "@/lib/types";

export type ProfilePayload = { first_name: string; last_name: string; phone: string; dni: string };

export function ProfileForm({ customer, onSave }: { customer: Customer; onSave?: (payload: ProfilePayload) => Promise<Customer> }) {
  const [values, setValues] = useState<ProfilePayload>({ ...customer.profile, dni: "" });
  const [saved, setSaved] = useState(customer);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const firstInput = useRef<HTMLInputElement>(null);
  const save = onSave ?? (async (payload) => apiRequest<Customer>("/customers/me/", {
    method: "PATCH",
    body: JSON.stringify({ ...payload, ...(payload.dni ? { dni: payload.dni } : {}) }),
  }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!values.first_name.trim()) next.first_name = "Ingresá tu nombre.";
    if (!values.last_name.trim()) next.last_name = "Ingresá tu apellido.";
    if (!values.phone.trim()) next.phone = "Ingresá un teléfono.";
    if (!saved.masked_dni && !/^\d{7,8}$/.test(values.dni)) next.dni = "Ingresá un DNI de 7 u 8 dígitos.";
    setErrors(next);
    if (Object.keys(next).length) { firstInput.current?.focus(); return; }
    setBusy(true);
    try {
      const result = await save(values);
      setSaved(result);
      setValues({ ...result.profile, dni: "" });
    } catch (cause) {
      if (cause instanceof ApiError) {
        setErrors({ form: cause.message, ...Object.fromEntries(Object.entries(cause.fields).map(([key, value]) => [key, value[0]])) });
      } else setErrors({ form: "No pudimos guardar el perfil." });
    } finally {
      setBusy(false);
    }
  };

  const field = (name: keyof ProfilePayload, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => {
    const errorId = `profile-${name}-error`;
    return <div><label htmlFor={`profile-${name}`}>{label}</label><input ref={name === "first_name" ? firstInput : undefined} id={`profile-${name}`} value={values[name]} onChange={(event) => setValues({ ...values, [name]: event.target.value })} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? errorId : undefined} {...props} />{errors[name] && <span id={errorId} className="field-error" role="alert">{errors[name]}</span>}</div>;
  };

  return <form className="form-stack profile-form" onSubmit={(event) => void submit(event)} noValidate><h3>Datos para comprar</h3><div className="field-pair">{field("first_name", "Nombre", { autoComplete: "given-name" })}{field("last_name", "Apellido", { autoComplete: "family-name" })}</div>{field("phone", "Teléfono", { type: "tel", autoComplete: "tel" })}{field("dni", "DNI", { inputMode: "numeric", placeholder: saved.masked_dni ? "Dejalo vacío para conservarlo" : "Solo números" })}{saved.masked_dni && <p className="success-message" role="status">DNI guardado: {saved.masked_dni}</p>}{errors.form && <p className="inline-error" role="alert">{errors.form}</p>}<button className="button primary" disabled={busy}>{busy ? "Guardando…" : "Guardar perfil"}</button></form>;
}
