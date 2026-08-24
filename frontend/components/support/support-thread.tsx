"use client";

import { useCallback, useEffect, useState } from "react";

import { supportApi } from "@/lib/support/api";
import type { SupportCaseDetail, SupportCaseStatus, SupportMessage } from "@/lib/support/types";

import { MessageComposer } from "./message-composer";
import { SupportAttachment } from "./support-attachment";

const statusLabels: Record<SupportCaseStatus, string> = {
  new: "Recibida",
  waiting_customer: "Esperando tu respuesta",
  waiting_staff: "En revisión",
  resolved: "Resuelta",
  closed: "Cerrada",
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Fecha no disponible" : date.toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });
}

function authorLabel(role: SupportMessage["author_role"]) {
  return role === "staff" ? "Equipo de atención" : "Vos";
}

function orderedMessages(messages: SupportMessage[]) {
  return [...messages].sort((first, second) => first.created_at.localeCompare(second.created_at) || first.id - second.id);
}

function messageFor(cause: unknown) {
  return cause instanceof Error ? cause.message : "No pudimos cargar la consulta. Intentá nuevamente.";
}

export function SupportThread({ publicId, pollIntervalMs = 30_000 }: { publicId: string; pollIntervalMs?: number }) {
  const [supportCase, setSupportCase] = useState<SupportCaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);

  const loadCase = useCallback(async (active: () => boolean = () => true) => {
    try {
      const detail = await supportApi.getCase(publicId);
      if (!active()) return;
      setSupportCase(detail);
      setError("");
      setNotFound(false);
    } catch (cause) {
      if (!active()) return;
      if (typeof cause === "object" && cause && "status" in cause && cause.status === 404) {
        setNotFound(true);
        setError("");
      } else {
        setError(messageFor(cause));
      }
    } finally {
      if (active()) setLoading(false);
    }
  }, [publicId]);

  useEffect(() => {
    let mounted = true;
    const active = () => mounted;
    void loadCase(active);
    const timer = window.setInterval(() => { void loadCase(active); }, pollIntervalMs);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [loadCase, pollIntervalMs]);

  if (loading && !supportCase) return <p role="status">Cargando la consulta...</p>;
  if (notFound) return <section className="support-thread"><h1>No encontramos esta consulta.</h1><p>Verificá el enlace o recuperá la consulta con tu número y código privado.</p></section>;
  if (error && !supportCase) return <section className="support-thread"><p className="inline-error" role="alert">{error} <button className="text-button" onClick={() => void loadCase()} type="button">Reintentar</button></p></section>;
  if (!supportCase) return null;

  const closed = supportCase.status === "closed";
  return <section aria-labelledby="support-thread-title" className="support-thread">
    <header>
      <p>{supportCase.case_number}</p>
      <h1 id="support-thread-title">{supportCase.subject}</h1>
      <p><strong>Estado:</strong> {statusLabels[supportCase.status]}</p>
    </header>
    {error ? <p className="inline-error" role="alert">{error}</p> : null}
    <ol aria-label="Mensajes de la consulta" className="support-message-list">
      {orderedMessages(supportCase.messages).map((message) => <li key={message.id}>
        <article className="support-message">
          <header><strong>{authorLabel(message.author_role)}</strong><time dateTime={message.created_at}>{formatDate(message.created_at)}</time></header>
          <p>{message.body}</p>
          {message.attachments.map((attachment) => <SupportAttachment attachment={attachment} key={attachment.public_id} />)}
        </article>
      </li>)}
    </ol>
    {closed ? <p role="status">Esta consulta está cerrada y no admite nuevas respuestas.</p> : <MessageComposer disabled={false} onSend={async (body, files, idempotencyKey) => {
      await supportApi.sendMessage(publicId, body, files, idempotencyKey);
      await loadCase();
    }} />}
  </section>;
}
