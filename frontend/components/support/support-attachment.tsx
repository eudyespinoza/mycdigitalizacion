"use client";

import { supportApi } from "@/lib/support/api";
import type { SupportAttachment as SupportAttachmentData } from "@/lib/support/types";

import { formatAttachmentSize } from "./attachment-queue";

function isImage(attachment: SupportAttachmentData) {
  return attachment.detected_mime_type === "image/jpeg"
    || attachment.detected_mime_type === "image/png"
    || attachment.detected_mime_type === "image/webp";
}

export function SupportAttachment({ attachment }: { attachment: SupportAttachmentData }) {
  const downloadUrl = supportApi.attachmentDownloadUrl(attachment.public_id);
  const previewUrl = isImage(attachment) ? supportApi.attachmentDownloadUrl(attachment.public_id, true) : "";
  return <section className="support-message-attachment">
    {previewUrl ? <a aria-label={`Abrir vista previa de ${attachment.original_name}`} href={previewUrl} target="_blank" rel="noreferrer"><img alt={`Vista previa de ${attachment.original_name}`} src={previewUrl} /></a> : null}
    <p>{attachment.original_name} <span>{formatAttachmentSize(attachment.size_bytes)}</span></p>
    <a download href={downloadUrl}>Descargar {attachment.original_name}</a>
  </section>;
}
