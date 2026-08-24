"use client";

import { Copy, WarningCircle } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { supportApi } from "@/lib/support/api";
import type { SupportCaseDetail, SupportCaseKind, SupportCaseStatus, SupportCaseSummary } from "@/lib/support/types";
import { CaseCreateDialog } from "./case-create-dialog";
import { CaseRecoveryDialog } from "./case-recovery-dialog";

type Mode = "idle" | "create" | "recover" | "confirmation";

const statusLabels: Record<SupportCaseStatus, string> = {
  new: "Recibida",
  waiting_customer: "Esperando tu respuesta",
  waiting_staff: "En revisión",
  resolved: "Resuelta",
  closed: "Cerrada",
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Actualización reciente" : date.toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" });
}

function mergeCase(cases: SupportCaseSummary[], next: SupportCaseSummary) {
  return [next, ...cases.filter((item) => item.public_id !== next.public_id)];
}

function CreatedConfirmation({ created, copied, onCopy, onDismiss }: {
  created: SupportCaseDetail;
  copied: boolean;
  onCopy: () => void;
  onDismiss: () => void;
}) {
  return <section aria-labelledby="support-created-title" className="support-created-panel" role="status">
    <WarningCircle aria-hidden="true" size={28} weight="bold" />
    <h2 id="support-created-title">{created.kind === "problem" ? "Problema reportado" : "Consulta creada"}</h2>
    <p>Tu número de {created.kind === "problem" ? "reporte" : "consulta"} es <strong>{created.case_number}</strong>.</p>
    {created.recovery_code ? <>
      <p>Guardá este código privado en un lugar seguro. Sólo se muestra una vez.</p>
      <p className="support-recovery-code"><strong>{created.recovery_code}</strong></p>
      <button className="button secondary" onClick={onCopy} type="button"><Copy aria-hidden="true" size={18} />{copied ? "Código copiado" : "Copiar código privado"}</button>
    </> : null}
    <button className="button primary" onClick={onDismiss} type="button">Entendido</button>
  </section>;
}

export function SupportHub({ initialKind }: { initialKind?: SupportCaseKind }) {
  const [mode, setMode] = useState<Mode>(initialKind ? "create" : "idle");
  const [cases, setCases] = useState<SupportCaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [created, setCreated] = useState<SupportCaseDetail | null>(null);
  const [copied, setCopied] = useState(false);
  const isProblemRoute = initialKind === "problem";

  const loadCases = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const availableCases = await supportApi.listCases("consultation");
      setCases(availableCases.filter((supportCase) => supportCase.kind === "consultation"));
    } catch (cause) {
      setLoadError(cause instanceof Error ? cause.message : "No pudimos cargar tus consultas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadCases(); }, [loadCases]);

  const createdCase = (next: SupportCaseDetail) => {
    setCases((current) => mergeCase(current, next));
    setCreated(next);
    setCopied(false);
    setMode("confirmation");
  };

  const recoveredCase = (next: SupportCaseDetail) => {
    setCases((current) => mergeCase(current, next));
    setMode("idle");
    void loadCases();
  };

  const copyRecoveryCode = async () => {
    if (!created?.recovery_code || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(created.recovery_code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const dismissConfirmation = () => {
    setCreated(null);
    setMode("idle");
  };

  if (isProblemRoute && mode !== "confirmation") {
    return <CaseCreateDialog kind="problem" onCreated={createdCase} presentation="panel" />;
  }

  if (isProblemRoute && created) {
    return <section className="support-hub"><CreatedConfirmation copied={copied} created={created} onCopy={() => void copyRecoveryCode()} onDismiss={dismissConfirmation} /></section>;
  }

  return <section className="support-hub">
    <header className="support-hub-header">
      <div>
        <h1>Mis consultas</h1>
        <p className="page-intro">Seguimos tus consultas y te avisamos cuando haya novedades.</p>
      </div>
      <div className="support-hub-actions">
        <button className="button primary" onClick={() => setMode("create")} type="button">Nueva consulta</button>
        <button className="text-button" onClick={() => setMode("recover")} type="button">Recuperar consulta</button>
      </div>
    </header>

    <section aria-label="Consultas accesibles" className="support-case-list">
      {loading ? <p role="status">Cargando tus consultas...</p> : null}
      {!loading && loadError ? <p className="inline-error" role="alert">{loadError} <button className="text-button" onClick={() => void loadCases()} type="button">Reintentar</button></p> : null}
      {!loading && !loadError && cases.length === 0 ? <div className="empty-state">
        <h2>Todavía no tenés consultas abiertas.</h2>
        <p>Cuando necesites ayuda, iniciá una consulta y vas a poder seguirla desde acá.</p>
      </div> : null}
      {!loading && !loadError && cases.length > 0 ? <div className="support-case-rows">
        {cases.map((supportCase) => <article className="support-case-row" key={supportCase.public_id}>
          <div>
            <strong>{supportCase.subject}</strong>
            <p>{supportCase.case_number}</p>
          </div>
          <div>
            <span>{statusLabels[supportCase.status] ?? "En actualización"}</span>
            <time dateTime={supportCase.updated_at}>Actualizada {formatDate(supportCase.updated_at)}</time>
          </div>
        </article>)}
      </div> : null}
    </section>

    {mode === "create" ? <CaseCreateDialog kind="consultation" onClose={() => setMode("idle")} onCreated={createdCase} presentation="dialog" /> : null}
    {mode === "recover" ? <CaseRecoveryDialog onClose={() => setMode("idle")} onRecovered={recoveredCase} /> : null}
    {mode === "confirmation" && created ? <CreatedConfirmation copied={copied} created={created} onCopy={() => void copyRecoveryCode()} onDismiss={dismissConfirmation} /> : null}
  </section>;
}
