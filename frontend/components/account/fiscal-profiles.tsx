"use client";

import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { BillingProfile } from "@/lib/types";

const emptyValues = {
  label: "",
  legal_name: "",
  tax_condition: "consumidor_final",
  cuit: "",
  is_default: false,
};

export function FiscalProfiles() {
  const [profiles, setProfiles] = useState<BillingProfile[]>([]);
  const [values, setValues] = useState(emptyValues);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setProfiles(await apiRequest<BillingProfile[]>("/billing-profiles/"));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "No pudimos cargar tus datos fiscales.",
      );
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest<BillingProfile>("/billing-profiles/", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setMessage("Perfil fiscal guardado.");
      setValues(emptyValues);
      await load();
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(cause.fields.cuit?.[0] ?? cause.message);
      } else {
        setError(cause instanceof Error ? cause.message : "No pudimos guardar el perfil.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="split-form">
      <section>
        <h2>Perfiles guardados</h2>
        {profiles.length ? profiles.map((profile) => (
          <article className="fiscal-row" key={profile.id}>
            <strong>{profile.label}</strong>
            <span>{profile.legal_name}</span>
            <span>{profile.masked_cuit}</span>
            {profile.is_default && <b>Predeterminado</b>}
          </article>
        )) : <p>No hay perfiles fiscales guardados.</p>}
      </section>
      <form className="form-stack" onSubmit={(event) => void submit(event)}>
        <h2>Nuevo perfil fiscal</h2>
        <label htmlFor="fiscal-label">Etiqueta</label>
        <input
          disabled={busy}
          id="fiscal-label"
          onChange={(event) => setValues({ ...values, label: event.target.value })}
          required
          value={values.label}
        />
        <label htmlFor="legal-name">Razón social o nombre</label>
        <input
          disabled={busy}
          id="legal-name"
          onChange={(event) => setValues({ ...values, legal_name: event.target.value })}
          required
          value={values.legal_name}
        />
        <label htmlFor="tax-condition">Condición fiscal</label>
        <select
          disabled={busy}
          id="tax-condition"
          onChange={(event) => setValues({ ...values, tax_condition: event.target.value })}
          value={values.tax_condition}
        >
          <option value="consumidor_final">Consumidor final</option>
          <option value="monotributista">Monotributista</option>
          <option value="responsable_inscripto">Responsable inscripto</option>
          <option value="exento">Exento</option>
        </select>
        <label htmlFor="cuit">CUIT o DNI</label>
        <input
          aria-describedby="fiscal-identifier-help"
          autoComplete="off"
          disabled={busy}
          id="cuit"
          inputMode="numeric"
          onChange={(event) => setValues({ ...values, cuit: event.target.value })}
          placeholder="20-12345678-6 o 12.345.678"
          required
          value={values.cuit}
        />
        <small id="fiscal-identifier-help">
          Si ingresás un DNI, buscaremos automáticamente su CUIT antes de validar los datos.
        </small>
        <label className="check-label">
          <input
            checked={values.is_default}
            disabled={busy}
            onChange={(event) => setValues({ ...values, is_default: event.target.checked })}
            type="checkbox"
          />
          Usar de forma predeterminada
        </label>
        {error && <p className="field-error" role="alert">{error}</p>}
        {message && <p className="success-message" role="status">{message}</p>}
        <button className="button primary" disabled={busy}>
          {busy ? "Validando con ARCA…" : "Guardar perfil"}
        </button>
      </form>
    </div>
  );
}
