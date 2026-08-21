"use client";

import Link from "next/link";
import { useState } from "react";

import { managementRequest } from "@/lib/management/api";
import type { ContentKind, ManagedContent } from "@/lib/management/content-types";


const labels: Record<ContentKind, string> = {
  hero: "Hero principal",
  promotions: "Carrusel de promociones",
  collections: "Colecciones",
  popups: "Popup de promociones",
};


export function ContentOverview({ content }: { content: Record<ContentKind, ManagedContent[]> }) {
  const [rows, setRows] = useState(content);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(kind: ContentKind, item: ManagedContent) {
    if (!window.confirm(`¿Eliminar “${item.title}”? Esta acción no se puede deshacer.`)) return;

    const key = `${kind}:${item.id}`;
    setDeleting(key);
    setError(null);
    try {
      await managementRequest<void>(`/content/${kind}/${item.id}/`, { method: "DELETE" });
      setRows((current) => ({
        ...current,
        [kind]: current[kind].filter((row) => row.id !== item.id),
      }));
    } catch {
      setError(key);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="management-content-sections">
      {(Object.keys(labels) as ContentKind[]).map((kind) => (
        <section className="management-form-section" key={kind}>
          <div className="management-section-heading">
            <div>
              <p className="management-kicker">Landing</p>
              <h2>{labels[kind]}</h2>
            </div>
            <Link className="button secondary" href={`/gestion/contenido/${kind}/nuevo`}>Agregar</Link>
          </div>
          {rows[kind].length ? (
            <ul className="management-simple-list">
              {rows[kind].map((item) => {
                const key = `${kind}:${item.id}`;
                return (
                  <li key={item.id}>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{item.enabled ? "Visible" : "Deshabilitado"} · orden {item.order}</small>
                    </span>
                    <div className="management-content-actions">
                      <Link href={`/gestion/contenido/${kind}/${item.id}`}>Editar</Link>
                      <button
                        aria-label={`Eliminar ${item.title}`}
                        className="button danger"
                        disabled={deleting === key}
                        onClick={() => void remove(kind, item)}
                        type="button"
                      >
                        {deleting === key ? "Eliminando…" : "Eliminar"}
                      </button>
                    </div>
                    {error === key ? (
                      <p className="inline-error management-content-error" role="alert">
                        No pudimos eliminar este contenido. Intentá nuevamente.
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p>Todavía no hay contenido en este bloque.</p>
          )}
        </section>
      ))}
    </div>
  );
}
