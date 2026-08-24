"use client";

import { FormEvent, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { ApiError } from "@/lib/api";
import { supportApi } from "@/lib/support/api";
import type { SupportCaseDetail } from "@/lib/support/types";

export function CaseRecoveryDialog({ onClose, onRecovered }: { onClose: () => void; onRecovered: (caseDetail: SupportCaseDetail) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const caseNumber = String(form.get("case_number") ?? "").trim();
    const code = String(form.get("code") ?? "");
    const nextErrors: Record<string, string> = {};
    if (!caseNumber) nextErrors.case_number = "Ingresá el número de consulta.";
    if (!code) nextErrors.code = "Ingresá el código privado.";
    setFieldErrors(nextErrors);
    setError("");
    if (Object.keys(nextErrors).length) return;
    setBusy(true);
    try {
      onRecovered(await supportApi.recoverCase(caseNumber, code));
    } catch (cause) {
      const apiError = cause instanceof ApiError ? cause : null;
      setFieldErrors(apiError ? Object.fromEntries(Object.entries(apiError.fields).map(([field, messages]) => [field, messages[0]])) : {});
      setError(cause instanceof Error ? cause.message : "No pudimos recuperar la consulta.");
    } finally {
      setBusy(false);
    }
  };

  return <ManagementFormDialog description="Usá el número de la consulta y el código privado que recibiste al crearla." onClose={() => { if (!busy) onClose(); }} open title="Recuperar consulta">
    <form className="form-stack support-recovery-form" noValidate onSubmit={(event) => void submit(event)}>
      <label htmlFor="support-case-number">Número de consulta</label>
      <input aria-describedby={fieldErrors.case_number ? "support-case-number-error" : undefined} aria-invalid={Boolean(fieldErrors.case_number)} id="support-case-number" name="case_number" required />
      {fieldErrors.case_number ? <span className="field-error" id="support-case-number-error" role="alert">{fieldErrors.case_number}</span> : null}
      <label htmlFor="support-recovery-code">Código privado</label>
      <input aria-describedby={fieldErrors.code ? "support-recovery-code-error" : undefined} aria-invalid={Boolean(fieldErrors.code)} autoComplete="off" id="support-recovery-code" name="code" required type="password" />
      {fieldErrors.code ? <span className="field-error" id="support-recovery-code-error" role="alert">{fieldErrors.code}</span> : null}
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <div className="support-form-actions">
        <button className="button primary" disabled={busy} type="submit">{busy ? "Recuperando..." : "Recuperar consulta"}</button>
        <button className="button secondary" disabled={busy} onClick={onClose} type="button">Cancelar</button>
      </div>
    </form>
  </ManagementFormDialog>;
}
