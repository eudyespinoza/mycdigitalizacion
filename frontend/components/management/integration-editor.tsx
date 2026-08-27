"use client";

import { CaretDown, CheckCircle, UploadSimple } from "@phosphor-icons/react";
import { FormEvent, useId, useState } from "react";

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
  if (field.type === "select") {
    return (
      <label className="integration-field">
        <span className="integration-field-heading">{field.label}</span>
        <select aria-label={field.label} defaultValue={String(value ?? "")} name={field.key}>
          {field.options?.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        {field.hint && <small>{field.hint}</small>}
      </label>
    );
  }
  if (field.type === "file") {
    return <FileField configured={configured} field={field} />;
  }
  return (
    <label className="integration-field">
      <span className="integration-field-heading">
        <span>{field.label}</span>
        {configured && <small className="secret-configured"><CheckCircle aria-hidden="true" size={15} weight="fill" />Configurada</small>}
      </span>
      <input
        aria-label={field.label}
        autoComplete="off"
        defaultValue={field.type === "password" ? "" : String(value ?? "")}
        name={field.key}
        placeholder={configured ? "Dejá vacío para conservarla" : ""}
        type={field.type ?? "text"}
      />
      {field.hint && <small>{field.hint}</small>}
    </label>
  );
}


function FileField({
  field,
  configured,
}: {
  field: IntegrationField;
  configured?: boolean;
}) {
  const inputId = useId();
  const [fileName, setFileName] = useState("");

  return (
    <div className="integration-field integration-file-field">
      <div className="integration-field-heading">
        <label htmlFor={inputId}>{field.label}</label>
        {configured && <small className="secret-configured"><CheckCircle aria-hidden="true" size={15} weight="fill" />Guardado</small>}
      </div>
      <div className="integration-file-control">
        <input
          accept={field.accept}
          aria-label={field.label}
          className="integration-file-input"
          id={inputId}
          name={field.key}
          onChange={(event) => setFileName(event.currentTarget.files?.[0]?.name ?? "")}
          type="file"
        />
        <label className="integration-file-trigger" htmlFor={inputId}>
          <UploadSimple aria-hidden="true" size={18} weight="bold" />
          Seleccionar archivo
        </label>
        <span className="integration-file-name" title={fileName || undefined}>
          {fileName || (configured ? "Archivo protegido guardado" : "Ningún archivo seleccionado")}
        </span>
      </div>
      {configured && <small>Seleccioná otro archivo sólo si querés reemplazar el actual.</small>}
      {field.hint && <small>{field.hint}</small>}
    </div>
  );
}


function readSecretFile(file: File, encoding: "text" | "base64") {
  if (!file.name || file.size === 0) return Promise.resolve("");
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("No pudimos leer el archivo."));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(encoding === "base64" ? result.split(",", 2)[1] ?? "" : result);
    };
    if (encoding === "base64") reader.readAsDataURL(file);
    else reader.readAsText(file);
  });
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
  const [arcaCredentialMethod, setArcaCredentialMethod] = useState<"pfx" | "pem">(() => (
    integration.secret_fields.pfx_base64
      ? "pfx"
      : integration.secret_fields.certificate_pem || integration.secret_fields.private_key_pem
        ? "pem"
        : "pfx"
  ));
  const definition = integrationFields[current.provider];
  const isArca = current.provider === "arca_a13";
  const arcaCuitField = isArca ? definition.public.find((field) => field.key === "represented_cuit") : undefined;
  const arcaEndpointFields = isArca
    ? definition.public.filter((field) => field.key === "wsaa_url" || field.key === "a13_url")
    : [];
  const visibleSecretFields = isArca
    ? definition.secrets.filter((field) => (
      arcaCredentialMethod === "pfx"
        ? field.key === "pfx_base64" || field.key === "pfx_password"
        : field.key === "certificate_pem" || field.key === "private_key_pem" || field.key === "private_key_passphrase"
    ))
    : definition.secrets;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const public_config = Object.fromEntries(
      definition.public.map((field) => {
        if (field.type === "boolean") return [field.key, form.has(field.key)];
        const value = String(form.get(field.key) ?? "");
        return [field.key, field.type === "number" && value ? Number(value) : value];
      }),
    );
    try {
      const secrets = Object.fromEntries(await Promise.all(
        definition.secrets.map(async (field) => {
          const value = form.get(field.key);
          if (field.type === "file") {
            const input = formElement.elements.namedItem(field.key);
            const file = input instanceof HTMLInputElement ? input.files?.[0] : undefined;
            return [
              field.key,
              file
                ? await readSecretFile(file, field.encoding ?? "text")
                : "",
            ];
          }
          return [field.key, String(value ?? "")];
        }),
      ));
      let clear_secret_fields: string[] | undefined;
      if (current.provider === "arca_a13") {
        if (secrets.pfx_base64) {
          clear_secret_fields = [
            "certificate_pem",
            "private_key_pem",
            "private_key_passphrase",
          ];
        } else if (secrets.certificate_pem && secrets.private_key_pem) {
          clear_secret_fields = ["pfx_base64", "pfx_password"];
        }
      }
      const next = await onSave({
        enabled: form.has("enabled"),
        environment: String(form.get("environment")) as IntegrationUpdate["environment"],
        public_config,
        secrets,
        ...(clear_secret_fields ? { clear_secret_fields } : {}),
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
    <form className={`management-form integration-editor${isArca ? " integration-editor-arca" : ""}`} onSubmit={(event) => void submit(event)}>
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
        {isArca ? (
          <div className="arca-public-configuration">
            {arcaCuitField && (
              <div className="arca-primary-field">
                <Field field={arcaCuitField} value={current.public_config[arcaCuitField.key] ?? ""} />
              </div>
            )}
            <details className="integration-advanced">
              <summary>
                <span>Configuración avanzada de endpoints</span>
                <CaretDown aria-hidden="true" size={18} weight="bold" />
              </summary>
              <p>Podés dejar estas URLs vacías para usar los servicios oficiales del ambiente seleccionado.</p>
              <div className="management-field-grid">
                {arcaEndpointFields.map((field) => (
                  <Field field={field} key={field.key} value={current.public_config[field.key] ?? ""} />
                ))}
              </div>
            </details>
          </div>
        ) : (
          <div className="management-field-grid">
            {definition.public.map((field) => (
              <Field field={field} key={field.key} value={current.public_config[field.key] ?? ""} />
            ))}
          </div>
        )}
      </section>
      {definition.secrets.length > 0 && (
        <section className="management-form-section">
          <h2>Credenciales protegidas</h2>
          <p>Los valores guardados no pueden volver a verse. Cargá uno sólo si necesitás reemplazarlo.</p>
          {isArca && (
            <fieldset className="arca-credential-method">
              <legend>Método de certificado</legend>
              <div className="arca-method-options">
                <label data-selected={arcaCredentialMethod === "pfx"}>
                  <input
                    checked={arcaCredentialMethod === "pfx"}
                    name="credential_method"
                    onChange={() => setArcaCredentialMethod("pfx")}
                    type="radio"
                    value="pfx"
                  />
                  <span><strong>Archivo PFX / P12</strong><small>Un único archivo protegido</small></span>
                </label>
                <label data-selected={arcaCredentialMethod === "pem"}>
                  <input
                    checked={arcaCredentialMethod === "pem"}
                    name="credential_method"
                    onChange={() => setArcaCredentialMethod("pem")}
                    type="radio"
                    value="pem"
                  />
                  <span><strong>Certificado + clave PEM</strong><small>Dos archivos independientes</small></span>
                </label>
              </div>
            </fieldset>
          )}
          <div className={`management-field-grid${isArca ? " arca-credential-fields" : ""}`}>
            {visibleSecretFields.map((field) => (
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
