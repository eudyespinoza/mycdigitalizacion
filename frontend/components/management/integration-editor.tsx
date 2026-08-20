"use client";

import { FormEvent, useState } from "react";

import { integrationFields, type IntegrationField } from "@/lib/management/integration-fields";
import type { IntegrationConfiguration, IntegrationUpdate } from "@/lib/management/types";


function Field({
  field,
  value,
  configured,
}: {
  field: IntegrationField;
  value: string | number | boolean;
  configured?: boolean;
}) {
  if (field.type === "boolean") {
    return (
      <label className="management-check">
        <input defaultChecked={Boolean(value)} name={field.key} type="checkbox" />
        <span>{field.label}</span>
      </label>
    );
  }
  return (
    <label>
      <span>{field.label}</span>
      {configured && <small className="secret-configured">Configurada</small>}
      <input
        aria-label={field.label}
        autoComplete="off"
        defaultValue={field.type === "password" ? "" : String(value ?? "")}
        name={field.key}
        placeholder={configured ? "Dejá vacío para conservarla" : ""}
        type={field.type ?? "text"}
      />
    </label>
  );
}


export function IntegrationEditor({
  integration,
  onSave,
  onTest,
}: {
  integration: IntegrationConfiguration;
  onSave: (payload: IntegrationUpdate) => Promise<IntegrationConfiguration>;
  onTest?: () => Promise<IntegrationConfiguration>;
}) {
  const [current, setCurrent] = useState(integration);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const definition = integrationFields[current.provider];

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    const form = new FormData(event.currentTarget);
    const public_config = Object.fromEntries(
      definition.public.map((field) => {
        if (field.type === "boolean") return [field.key, form.has(field.key)];
        const value = String(form.get(field.key) ?? "");
        return [field.key, field.type === "number" && value ? Number(value) : value];
      }),
    );
    const secrets = Object.fromEntries(
      definition.secrets.map((field) => [field.key, String(form.get(field.key) ?? "")]),
    );
    try {
      const next = await onSave({
        enabled: form.has("enabled"),
        environment: String(form.get("environment")) as IntegrationUpdate["environment"],
        public_config,
        secrets,
      });
      setCurrent(next);
      setState("saved");
    } catch {
      setState("error");
    }
  };

  const testConnection = async () => {
    if (!onTest) return;
    setState("saving");
    try {
      setCurrent(await onTest());
      setState("saved");
    } catch {
      setState("error");
    }
  };

  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <div className="management-form-section integration-enable-row">
        <label className="management-check">
          <input defaultChecked={current.enabled} name="enabled" type="checkbox" />
          <span>Integración habilitada</span>
        </label>
        <label>
          <span>Ambiente</span>
          <select defaultValue={current.environment} name="environment">
            <option value="sandbox">Pruebas</option>
            <option value="qa">QA</option>
            <option value="production">Producción</option>
          </select>
        </label>
      </div>
      <section className="management-form-section">
        <h2>Datos de la integración</h2>
        <div className="management-field-grid">
          {definition.public.map((field) => (
            <Field field={field} key={field.key} value={current.public_config[field.key] ?? ""} />
          ))}
        </div>
      </section>
      {definition.secrets.length > 0 && (
        <section className="management-form-section">
          <h2>Credenciales protegidas</h2>
          <p>Los valores guardados no pueden volver a verse. Escribí uno sólo para reemplazarlo.</p>
          <div className="management-field-grid">
            {definition.secrets.map((field) => (
              <Field
                configured={current.secret_fields[field.key]}
                field={field}
                key={field.key}
                value=""
              />
            ))}
          </div>
        </section>
      )}
      {current.last_test_message && <p className="management-notice">{current.last_test_message}</p>}
      {state === "error" && <p className="inline-error">No pudimos guardar. Revisá los datos e intentá nuevamente.</p>}
      {state === "saved" && <p className="success-message">Cambios guardados.</p>}
      <div className="management-form-actions">
        <button className="button primary" disabled={state === "saving"} type="submit">
          {state === "saving" ? "Guardando…" : "Guardar configuración"}
        </button>
        {onTest && (
          <button className="button secondary" onClick={() => void testConnection()} type="button">
            Verificar configuración
          </button>
        )}
      </div>
    </form>
  );
}
