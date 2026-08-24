"use client";

import { useEffect, useState } from "react";

export const MAX_ATTACHMENTS = 5;
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
export const MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024;

export type AttachmentQueueResult = { files: File[]; error?: string };

const allowedTypes: Record<string, string[]> = {
  ".jpg": ["image/jpeg"],
  ".jpeg": ["image/jpeg"],
  ".png": ["image/png"],
  ".webp": ["image/webp"],
  ".pdf": ["application/pdf"],
  ".txt": ["text/plain"],
  ".csv": ["text/csv", "application/csv", "application/vnd.ms-excel"],
  ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
};

function extension(name: string) {
  const index = name.lastIndexOf(".");
  return index === -1 ? "" : name.slice(index).toLowerCase();
}

function fingerprint(file: File) {
  return `${file.name}:${file.size}:${file.type}:${file.lastModified}`;
}

function isAllowedFile(file: File) {
  const types = allowedTypes[extension(file.name)];
  return Boolean(types && (!file.type || types.includes(file.type.toLowerCase())));
}

function isPreviewableImage(file: File) {
  return ["image/jpeg", "image/png", "image/webp"].includes(file.type.toLowerCase())
    && [".jpg", ".jpeg", ".png", ".webp"].includes(extension(file.name));
}

export function formatAttachmentSize(size: number) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.ceil(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toLocaleString("es-AR", { maximumFractionDigits: 1 })} MB`;
}

export function mergeAttachmentQueue(current: File[], incoming: File[]): AttachmentQueueResult {
  const existing = new Set(current.map(fingerprint));
  const additions = incoming.filter((file) => {
    const key = fingerprint(file);
    if (existing.has(key)) return false;
    existing.add(key);
    return true;
  });

  if (current.length + additions.length > MAX_ATTACHMENTS) {
    return { files: current, error: "Podés adjuntar hasta 5 archivos por mensaje." };
  }
  const invalid = additions.find((file) => !isAllowedFile(file));
  if (invalid) {
    return { files: current, error: `El archivo «${invalid.name}» no tiene un formato permitido.` };
  }
  const tooLarge = additions.find((file) => file.size > MAX_FILE_SIZE_BYTES);
  if (tooLarge) {
    return { files: current, error: `El archivo «${tooLarge.name}» supera el máximo de 10 MB por archivo.` };
  }
  if ([...current, ...additions].reduce((total, file) => total + file.size, 0) > MAX_TOTAL_SIZE_BYTES) {
    return { files: current, error: "Los adjuntos superan el máximo total de 30 MB por mensaje." };
  }
  return { files: [...current, ...additions] };
}

type Preview = { key: string; url: string };

export function AttachmentQueue({ files, onRemove }: { files: File[]; onRemove: (file: File) => void }) {
  const [previews, setPreviews] = useState<Preview[]>([]);

  useEffect(() => {
    const next = files.flatMap((file) => {
      if (!isPreviewableImage(file) || typeof URL.createObjectURL !== "function") return [];
      return [{ key: fingerprint(file), url: URL.createObjectURL(file) }];
    });
    setPreviews(next);
    return () => next.forEach(({ url }) => URL.revokeObjectURL(url));
  }, [files]);

  if (!files.length) return null;
  return <ul aria-label="Adjuntos seleccionados" className="support-attachment-queue">
    {files.map((file) => {
      const preview = previews.find((item) => item.key === fingerprint(file));
      return <li key={fingerprint(file)} className="support-attachment-queue-item">
        {preview ? <img alt={`Vista previa de ${file.name}`} src={preview.url} /> : null}
        <span><strong>{file.name}</strong> <span>{formatAttachmentSize(file.size)}</span></span>
        <button aria-label={`Quitar ${file.name}`} className="text-button" onClick={() => onRemove(file)} type="button">Quitar</button>
      </li>;
    })}
  </ul>;
}
