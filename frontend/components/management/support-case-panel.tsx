"use client";

import { useState } from "react";

import { MessageComposer } from "@/components/support/message-composer";
import { managementRequest, managementSupportAttachmentDownloadUrl } from "@/lib/management/api";
import type { ManagementStaffUser } from "@/lib/management/access-types";
import type { ManagementSupportCaseDetail, ManagementSupportMessage } from "@/lib/management/support-types";

import { managementSupportLabels } from "./support-inbox";

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Fecha no disponible" : new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" }).format(date).replace(/[\u00a0\u202f]/g, " ");
}

function staffName(user: ManagementStaffUser) {
  return [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email;
}

function attachmentLink(publicId: string, preview = false) {
  return managementSupportAttachmentDownloadUrl(publicId, preview);
}

export function ManagementSupportCasePanel({ initialCase, staff }: { initialCase: ManagementSupportCaseDetail; staff: ManagementStaffUser[] }) {
  const [supportCase, setSupportCase] = useState(initialCase);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function patch(change: Record<string, string | number | null>) {
    setBusy(true);
    setError("");
    try {
      const updated = await managementRequest<ManagementSupportCaseDetail>(`/support/cases/${supportCase.public_id}/`, { method: "PATCH", body: JSON.stringify(change) });
      setSupportCase(updated);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos guardar los cambios. Intentá nuevamente.");
    } finally {
      setBusy(false);
    }
  }

  async function reply(body: string, files: File[], idempotencyKey: string) {
    setError("");
    const form = new FormData();
    form.append("body", body);
    form.append("idempotency_key", idempotencyKey);
    files.forEach((file) => form.append("attachments", file));
    try {
      const message = await managementRequest<ManagementSupportMessage>(`/support/cases/${supportCase.public_id}/messages/`, { method: "POST", body: form });
      setSupportCase((current) => ({ ...current, messages: [...current.messages, message], updated_at: message.created_at, message_count: current.message_count + 1 }));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "No pudimos enviar la respuesta. Intentá nuevamente.";
      setError(message);
      throw new Error(message);
    }
  }

  const closed = supportCase.status === "closed";
  return <section className="management-list-section" aria-labelledby="management-support-case-title">
    <header className="management-section-heading"><div><p>{supportCase.case_number}</p><h1 id="management-support-case-title">{supportCase.subject}</h1><p>{managementSupportLabels.kindLabels[supportCase.kind]} · {supportCase.contact_name || supportCase.contact_email || "Sin contacto"}</p></div></header>
    {error ? <p className="inline-error" role="alert">{error}</p> : null}
    <dl className="management-details"><div><dt>Contacto</dt><dd>{supportCase.contact_name || "Sin nombre"}<br />{supportCase.contact_email || "Sin email"}{supportCase.contact_phone ? <><br />{supportCase.contact_phone}</> : null}</dd></div><div><dt>Pedido</dt><dd>{supportCase.order_id ? `Pedido #${supportCase.order_id}` : "Sin pedido asociado"}</dd></div><div><dt>Producto</dt><dd>{supportCase.product_id ? `Producto #${supportCase.product_id}` : "Sin producto asociado"}</dd></div>{supportCase.source_url ? <div><dt>Origen</dt><dd><a href={supportCase.source_url} rel="noreferrer" target="_blank">Ver página de origen</a></dd></div> : null}</dl>
    <div className="management-content-actions" aria-label="Operaciones del caso">
      <label>Estado del caso<select disabled={busy} onChange={(event) => void patch({ status: event.target.value })} value={supportCase.status}>{Object.entries(managementSupportLabels.statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Prioridad del caso<select disabled={busy} onChange={(event) => void patch({ priority: event.target.value })} value={supportCase.priority}>{Object.entries(managementSupportLabels.priorityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Asignar a<select disabled={busy} onChange={(event) => void patch({ assigned_to: event.target.value ? Number(event.target.value) : null })} value={supportCase.assigned_to?.id ?? ""}><option value="">Sin asignar</option>{staff.filter((user) => user.is_active).map((user) => <option key={user.id} value={user.id}>{staffName(user)}</option>)}</select></label>
    </div>
    <ol aria-label="Mensajes del caso" className="support-message-list">{[...supportCase.messages].sort((left, right) => left.created_at.localeCompare(right.created_at) || left.id - right.id).map((message) => <li key={message.id}><article className="support-message"><header><strong>{message.author_role === "staff" ? message.author?.name || "Equipo de atención" : message.author?.name || "Cliente"}</strong><time dateTime={message.created_at}>{dateLabel(message.created_at)}</time></header><p>{message.body}</p>{message.attachments.map((attachment) => <p key={attachment.public_id}><a download href={attachmentLink(attachment.public_id)}>Descargar {attachment.original_name}</a></p>)}</article></li>)}</ol>
    {closed ? <p role="status">Este caso está cerrado y no admite nuevas respuestas.</p> : <MessageComposer disabled={busy} onSend={reply} />}
  </section>;
}
