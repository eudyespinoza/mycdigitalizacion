"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { ApiError } from "@/lib/api";
import { createSupportIdempotencyKey, supportApi } from "@/lib/support/api";
import type { SupportCaseDetail, SupportCaseKind, SupportConfiguration } from "@/lib/support/types";

type FieldErrors = Record<string, string>;

const categoryLabels: Record<string, string> = {
  productos: "Productos",
  compra: "Compra",
  envios: "Envíos",
  pagos: "Pagos",
  facturacion: "Facturación",
  otra: "Otra consulta",
  pedido: "Pedido",
  pago: "Pago",
  envio: "Envío",
  producto: "Producto",
  cuenta: "Cuenta",
  sitio: "Sitio web",
  otro: "Otro problema",
};

function readFieldErrors(error: unknown): FieldErrors {
  if (error instanceof ApiError) {
    return Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [field, messages[0]]));
  }
  return {};
}

function titleFor(kind: SupportCaseKind) {
  return kind === "problem" ? "Reportar un problema" : "Nueva consulta";
}

function subjectLabel(kind: SupportCaseKind) {
  return kind === "problem" ? "¿Qué problema encontraste?" : "¿En qué podemos ayudarte?";
}

type CaseCreateDialogProps = {
  kind: SupportCaseKind;
  presentation: "dialog" | "panel";
  onClose?: () => void;
  onCreated: (created: SupportCaseDetail) => void;
};

export function CaseCreateDialog({ kind, presentation, onClose, onCreated }: CaseCreateDialogProps) {
  const [configuration, setConfiguration] = useState<SupportConfiguration | null>(null);
  const [configurationError, setConfigurationError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [attachments, setAttachments] = useState<File[]>([]);
  const title = titleFor(kind);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const subjectInputRef = useRef<HTMLInputElement>(null);
  const focusedDialogSubject = useRef(false);
  const idempotencyKey = useRef("");

  useEffect(() => {
    let active = true;
    supportApi.configuration()
      .then((next) => {
        if (active) setConfiguration(next);
      })
      .catch((cause) => {
        if (active) setConfigurationError(cause instanceof Error ? cause.message : "No pudimos preparar el formulario.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (presentation !== "panel" || !configuration) return;
    headingRef.current?.focus();
  }, [configuration, presentation]);

  useEffect(() => {
    if (presentation !== "dialog" || !configuration || focusedDialogSubject.current) return;
    const frame = requestAnimationFrame(() => {
      if (!focusedDialogSubject.current) {
        subjectInputRef.current?.focus();
        focusedDialogSubject.current = true;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [configuration, presentation]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!configuration) return;
    const form = new FormData(event.currentTarget);
    const values = {
      contact_name: String(form.get("contact_name") ?? "").trim(),
      contact_email: String(form.get("contact_email") ?? "").trim(),
      subject: String(form.get("subject") ?? "").trim(),
      category: String(form.get("category") ?? ""),
      body: String(form.get("body") ?? "").trim(),
    };
    const nextErrors: FieldErrors = {};
    if (!values.subject) nextErrors.subject = "Ingresá un asunto.";
    if (!values.category) nextErrors.category = "Elegí una categoría.";
    if (!values.body) nextErrors.body = "Escribí un mensaje.";
    if (!configuration.authenticated) {
      if (!values.contact_name) nextErrors.contact_name = "Ingresá tu nombre.";
      if (!values.contact_email) nextErrors.contact_email = "Ingresá tu email.";
    }
    if (attachments.length > configuration.limits.max_files) nextErrors.attachments = `Podés adjuntar hasta ${configuration.limits.max_files} archivos.`;
    if (attachments.some((attachment) => attachment.size > configuration.limits.max_file_size_bytes)) nextErrors.attachments = "Cada archivo debe respetar el tamaño máximo permitido.";
    if (attachments.reduce((total, attachment) => total + attachment.size, 0) > configuration.limits.max_total_size_bytes) nextErrors.attachments = "El conjunto de archivos supera el tamaño máximo permitido.";
    setFieldErrors(nextErrors);
    setFormError("");
    if (Object.keys(nextErrors).length) return;

    setSubmitting(true);
    try {
      if (!idempotencyKey.current) idempotencyKey.current = createSupportIdempotencyKey();
      const created = await supportApi.createCase({
        kind,
        subject: values.subject,
        category: values.category,
        body: values.body,
        contact_name: values.contact_name || undefined,
        contact_email: values.contact_email || undefined,
        contact_phone: String(form.get("contact_phone") ?? "").trim() || undefined,
        source_url: kind === "problem" ? window.location.href : undefined,
        attachments,
        idempotency_key: idempotencyKey.current,
      });
      onCreated(created);
    } catch (cause) {
      const nextErrors = readFieldErrors(cause);
      setFieldErrors(nextErrors);
      setFormError(cause instanceof Error ? cause.message : "No pudimos enviar tu consulta. Intentá nuevamente.");
    } finally {
      setSubmitting(false);
    }
  };

  const form = configuration ? (
    <form className="form-stack support-case-form" noValidate onSubmit={(event) => void submit(event)}>
      {!configuration.authenticated ? <>
        <label htmlFor="support-contact-name">Nombre</label>
        <input aria-describedby={fieldErrors.contact_name ? "support-contact-name-error" : undefined} aria-invalid={Boolean(fieldErrors.contact_name)} autoComplete="name" id="support-contact-name" name="contact_name" required />
        {fieldErrors.contact_name ? <span className="field-error" id="support-contact-name-error" role="alert">{fieldErrors.contact_name}</span> : null}
        <label htmlFor="support-contact-email">Email</label>
        <input aria-describedby={fieldErrors.contact_email ? "support-contact-email-error" : undefined} aria-invalid={Boolean(fieldErrors.contact_email)} autoComplete="email" id="support-contact-email" name="contact_email" required type="email" />
        {fieldErrors.contact_email ? <span className="field-error" id="support-contact-email-error" role="alert">{fieldErrors.contact_email}</span> : null}
        <label htmlFor="support-contact-phone">Teléfono (opcional)</label>
        <input autoComplete="tel" id="support-contact-phone" name="contact_phone" type="tel" />
      </> : null}
      <label htmlFor="support-subject">Asunto</label>
      <input aria-describedby={fieldErrors.subject ? "support-subject-error" : undefined} aria-invalid={Boolean(fieldErrors.subject)} id="support-subject" name="subject" placeholder={subjectLabel(kind)} ref={subjectInputRef} required />
      {fieldErrors.subject ? <span className="field-error" id="support-subject-error" role="alert">{fieldErrors.subject}</span> : null}
      <label htmlFor="support-category">Categoría</label>
      <select aria-describedby={fieldErrors.category ? "support-category-error" : undefined} aria-invalid={Boolean(fieldErrors.category)} defaultValue="" id="support-category" name="category" required>
        <option disabled value="">Elegí una categoría</option>
        {configuration.categories[kind].map((category) => <option key={category} value={category}>{categoryLabels[category] ?? category}</option>)}
      </select>
      {fieldErrors.category ? <span className="field-error" id="support-category-error" role="alert">{fieldErrors.category}</span> : null}
      <label htmlFor="support-body">Mensaje</label>
      <textarea aria-describedby={fieldErrors.body ? "support-body-error" : undefined} aria-invalid={Boolean(fieldErrors.body)} id="support-body" name="body" required />
      {fieldErrors.body ? <span className="field-error" id="support-body-error" role="alert">{fieldErrors.body}</span> : null}
      <label htmlFor="support-attachments">Adjuntos (opcional)</label>
      <input accept="image/jpeg,image/png,image/webp,application/pdf,text/plain,text/csv,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" aria-describedby={fieldErrors.attachments ? "support-attachments-error" : undefined} aria-invalid={Boolean(fieldErrors.attachments)} id="support-attachments" multiple name="attachments" onChange={(event) => setAttachments(Array.from(event.currentTarget.files ?? []))} type="file" />
      {fieldErrors.attachments ? <span className="field-error" id="support-attachments-error" role="alert">{fieldErrors.attachments}</span> : null}
      <p className="helper">Hasta {configuration.limits.max_files} archivos por mensaje.</p>
      {formError ? <p className="inline-error" role="alert">{formError}</p> : null}
      <div className="support-form-actions">
        <button className="button primary" disabled={submitting} type="submit">{submitting ? "Enviando..." : kind === "problem" ? "Enviar reporte" : "Enviar consulta"}</button>
        {onClose ? <button className="button secondary" disabled={submitting} onClick={onClose} type="button">Cancelar</button> : null}
      </div>
    </form>
  ) : configurationError ? <p className="inline-error" role="alert">{configurationError}</p> : <p role="status">Preparando el formulario...</p>;

  if (presentation === "panel") {
    return <section aria-labelledby="support-create-title" className="support-create-panel">
      <h1 id="support-create-title" ref={headingRef} tabIndex={-1}>{title}</h1>
      <p className="page-intro">Contanos lo que pasó y te ayudamos desde esta misma conversación.</p>
      {form}
    </section>;
  }

  return <ManagementFormDialog description="Completá los datos para que podamos responderte." onClose={() => { if (!submitting) onClose?.(); }} open size="default" title={title}>{form}</ManagementFormDialog>;
}
