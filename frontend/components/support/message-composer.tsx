"use client";

import type { ClipboardEvent as ReactClipboardEvent, DragEvent, ChangeEvent, FormEvent } from "react";
import { useRef, useState } from "react";

import { AttachmentQueue, mergeAttachmentQueue } from "./attachment-queue";
import { createSupportIdempotencyKey } from "@/lib/support/api";

const acceptedFiles = ".jpg,.jpeg,.png,.webp,.pdf,.txt,.csv,.docx,.xlsx,image/jpeg,image/png,image/webp,application/pdf,text/plain,text/csv,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function filesFromClipboard(event: ClipboardEvent): File[] {
  return Array.from(event.clipboardData?.items ?? [])
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
}

export function MessageComposer({ disabled, onSend }: {
  disabled: boolean;
  onSend: (body: string, files: File[], idempotencyKey: string) => Promise<void>;
}) {
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const idempotencyKey = useRef<string | null>(null);

  const addFiles = (incoming: File[]) => {
    const result = mergeAttachmentQueue(files, incoming);
    setError(result.error ?? "");
    if (!result.error) setFiles(result.files);
  };

  const onChoose = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  };

  const onPaste = (event: ReactClipboardEvent<HTMLTextAreaElement>) => {
    const pastedFiles = filesFromClipboard(event.nativeEvent);
    if (pastedFiles.length) addFiles(pastedFiles);
  };

  const onDrop = (event: DragEvent<HTMLTextAreaElement>) => {
    event.preventDefault();
    setDragging(false);
    addFiles(Array.from(event.dataTransfer.files ?? []));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = body.trim();
    if (!message) {
      setError("Escribí un mensaje antes de enviarlo.");
      return;
    }
    setError("");
    setSending(true);
    try {
      const key = idempotencyKey.current ?? createSupportIdempotencyKey();
      idempotencyKey.current = key;
      await onSend(message, files, key);
      setBody("");
      setFiles([]);
      idempotencyKey.current = null;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos enviar el mensaje. Intentá nuevamente.");
    } finally {
      setSending(false);
    }
  };

  return <form className="support-message-composer" onSubmit={submit}>
    <label htmlFor="support-message">Mensaje</label>
    <textarea
      aria-describedby={error ? "support-message-error" : undefined}
      disabled={disabled || sending}
      id="support-message"
      onChange={(event) => setBody(event.target.value)}
      onDragLeave={() => setDragging(false)}
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDrop={onDrop}
      onPaste={onPaste}
      placeholder="Escribí tu respuesta"
      value={body}
    />
    <p aria-live="polite" className="support-drop-hint">{dragging ? "Soltá los archivos para adjuntarlos." : "Podés adjuntar archivos, arrastrarlos o pegarlos desde el portapapeles."}</p>
    <input accept={acceptedFiles} disabled={disabled || sending} id="support-attachments" multiple onChange={onChoose} ref={inputRef} type="file" />
    <label htmlFor="support-attachments">Adjuntar archivos</label>
    <AttachmentQueue files={files} onRemove={(file) => setFiles((current) => current.filter((item) => item !== file))} />
    {error ? <p className="inline-error" id="support-message-error" role="alert">{error} <button className="text-button" disabled={sending} type="submit">Reintentar</button></p> : null}
    <button className="button primary" disabled={disabled || sending} type="submit">{sending ? "Enviando mensaje..." : "Enviar mensaje"}</button>
  </form>;
}
