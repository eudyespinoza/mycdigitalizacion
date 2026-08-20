"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";

import { normalizeMediaUrl } from "@/lib/api";
import type { ManagementProductMedia } from "@/lib/management/catalog-types";

export function ProductMediaManager({
  initialMedia,
  onCreate,
  onUpdate,
  onDelete,
}: {
  initialMedia: ManagementProductMedia[];
  onCreate: (form: FormData) => Promise<ManagementProductMedia>;
  onUpdate: (id: number, form: FormData) => Promise<ManagementProductMedia>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [media, setMedia] = useState(initialMedia);
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    setState("saving");
    try {
      const created = await onCreate(new FormData(form));
      setMedia((rows) => [...rows, created].sort((a, b) => a.order - b.order));
      form.reset();
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const update = async (event: FormEvent<HTMLFormElement>, id: number) => {
    event.preventDefault();
    setState("saving");
    try {
      const updated = await onUpdate(id, new FormData(event.currentTarget));
      setMedia((rows) => rows.map((row) => row.id === id ? updated : row).sort((a, b) => a.order - b.order));
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const remove = async (id: number) => {
    setState("saving");
    try {
      await onDelete(id);
      setMedia((rows) => rows.filter((row) => row.id !== id));
      setState("idle");
    } catch {
      setState("error");
    }
  };

  return (
    <section className="management-form-section management-product-media">
      <div><h2>Imágenes del producto</h2><p>La primera imagen se usa como portada. Podés cambiar el orden y el texto descriptivo.</p></div>
      <div className="management-media-grid">
        {media.map((item) => (
          <article className="management-media-card" key={item.id}>
            <div className="management-media-preview"><Image alt={item.alt_text} fill sizes="240px" src={normalizeMediaUrl(item.file_url)} /></div>
            <form className="compact-management-form" onSubmit={(event) => void update(event, item.id)}>
              <label><span>Texto alternativo</span><input defaultValue={item.alt_text} name="alt_text" required /></label>
              <label><span>Orden</span><input defaultValue={item.order} min="0" name="order" type="number" /></label>
              <div className="management-form-actions"><button className="button secondary" type="submit">Guardar imagen</button><button className="button text danger" onClick={() => void remove(item.id)} type="button">Eliminar</button></div>
            </form>
          </article>
        ))}
      </div>
      <form className="compact-management-form management-media-upload" onSubmit={(event) => void create(event)}>
        <h3>Agregar imagen</h3>
        <label><span>Archivo</span><input accept="image/png,image/jpeg,image/webp,image/avif" name="file" required type="file" /></label>
        <label><span>Texto alternativo</span><input name="alt_text" placeholder="Describí lo que se ve en la imagen" required /></label>
        <label><span>Orden</span><input defaultValue={media.length} min="0" name="order" type="number" /></label>
        <button className="button secondary" disabled={state === "saving"} type="submit">{state === "saving" ? "Guardando…" : "Subir imagen"}</button>
      </form>
      {state === "error" && <p className="inline-error">No pudimos guardar la imagen. Revisá el archivo y volvé a intentar.</p>}
    </section>
  );
}
