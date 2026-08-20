"use client";

import { FormEvent, useState } from "react";

import type { GeneralSettings } from "@/lib/management/types";


export function GeneralSettingsForm({
  initial,
  onSave,
}: {
  initial: GeneralSettings;
  onSave: (settings: GeneralSettings) => Promise<void>;
}) {
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    const form = new FormData(event.currentTarget);
    const payload: GeneralSettings = {
      public_name: String(form.get("public_name") ?? ""),
      announcement: String(form.get("announcement") ?? ""),
      contact_email: String(form.get("contact_email") ?? ""),
      pickup_enabled: form.has("pickup_enabled"),
      pickup_label: String(form.get("pickup_label") ?? ""),
      pickup_address: String(form.get("pickup_address") ?? ""),
      pickup_hours: String(form.get("pickup_hours") ?? ""),
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
        <h2>Datos de la tienda</h2>
        <div className="management-field-grid">
          <label><span>Nombre público</span><input defaultValue={initial.public_name} name="public_name" /></label>
          <label><span>Email de contacto</span><input defaultValue={initial.contact_email} name="contact_email" type="email" /></label>
          <label className="field-wide"><span>Franja informativa</span><input defaultValue={initial.announcement} name="announcement" /></label>
        </div>
      </section>
      <section className="management-form-section">
        <h2>Retiro</h2>
        <label className="management-check"><input defaultChecked={initial.pickup_enabled} name="pickup_enabled" type="checkbox" /><span>Permitir retiro</span></label>
        <div className="management-field-grid">
          <label><span>Nombre de la opción</span><input defaultValue={initial.pickup_label} name="pickup_label" /></label>
          <label><span>Dirección</span><input defaultValue={initial.pickup_address} name="pickup_address" /></label>
          <label className="field-wide"><span>Horarios</span><input defaultValue={initial.pickup_hours} name="pickup_hours" /></label>
        </div>
      </section>
      {state === "saved" && <p className="success-message">Cambios guardados.</p>}
      {state === "error" && <p className="inline-error">No pudimos guardar los cambios.</p>}
      <button className="button primary" disabled={state === "saving"} type="submit">
        {state === "saving" ? "Guardando…" : "Guardar cambios"}
      </button>
    </form>
  );
}
