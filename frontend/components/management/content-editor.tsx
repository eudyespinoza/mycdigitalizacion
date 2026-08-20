"use client";

import { FormEvent, useState } from "react";

import type { ContentKind, ContentPayload, ManagedContent } from "@/lib/management/content-types";


const defaults: Omit<ContentPayload, "title"> = {
  enabled: true,
  order: 0,
  starts_at: null,
  ends_at: null,
  alt_text: "",
  cta_label: "",
  cta_url: "",
  focal_x: "50",
  focal_y: "50",
  safe_height_mobile: 320,
  safe_height_tablet: 420,
  safe_height_desktop: 520,
};


export function ContentEditor({
  kind,
  initial,
  onSave,
}: {
  kind: ContentKind;
  initial?: ManagedContent;
  onSave: (payload: ContentPayload) => Promise<void>;
}) {
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const values = { ...defaults, ...initial };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const desktop = form.get("desktop_image");
    const mobile = form.get("mobile_image");
    const payload: ContentPayload = {
      title: String(form.get("title")),
      body: String(form.get("body") ?? ""),
      enabled: form.has("enabled"),
      order: Number(form.get("order")),
      starts_at: String(form.get("starts_at") ?? "") || null,
      ends_at: String(form.get("ends_at") ?? "") || null,
      alt_text: String(form.get("alt_text") ?? ""),
      cta_label: String(form.get("cta_label") ?? ""),
      cta_url: String(form.get("cta_url") ?? ""),
      focal_x: String(form.get("focal_x")),
      focal_y: String(form.get("focal_y")),
      safe_height_mobile: Number(form.get("safe_height_mobile")),
      safe_height_tablet: Number(form.get("safe_height_tablet")),
      safe_height_desktop: Number(form.get("safe_height_desktop")),
      ...(kind === "hero" || kind === "promotions" ? {
        interval_ms: Number(form.get("interval_ms")),
        pause_on_reduced_motion: form.has("pause_on_reduced_motion"),
      } : {}),
      ...(kind === "collections" ? {
        product_ids: String(form.get("product_ids") ?? "").split(",").map((id) => Number(id.trim())).filter(Boolean),
      } : {}),
      ...(kind === "popups" ? {
        frequency: String(form.get("frequency")),
        display_delay_ms: Number(form.get("display_delay_ms")),
        dismissible: form.has("dismissible"),
        version: Number(form.get("version")),
      } : {}),
      ...(desktop instanceof File && desktop.size ? { desktop_image: desktop } : {}),
      ...(mobile instanceof File && mobile.size ? { mobile_image: mobile } : {}),
    };
    setState("saving");
    try {
      await onSave(payload);
      setState("saved");
    } catch {
      setState("error");
    }
  };
  const formatDate = (value: string | null | undefined) => value ? value.slice(0, 16) : "";
  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <section className="management-form-section">
        <h2>Contenido</h2>
        <div className="management-field-grid">
          <label className="field-wide"><span>Título</span><input defaultValue={values.title} name="title" required /></label>
          <label className="field-wide"><span>Texto</span><textarea defaultValue={values.body ?? ""} name="body" rows={4} /></label>
          <label><span>Orden</span><input defaultValue={values.order} min="0" name="order" type="number" /></label>
          <label className="management-check"><input defaultChecked={values.enabled} name="enabled" type="checkbox" /><span>Contenido habilitado</span></label>
          <label><span>Inicio</span><input defaultValue={formatDate(values.starts_at)} name="starts_at" type="datetime-local" /></label>
          <label><span>Fin</span><input defaultValue={formatDate(values.ends_at)} name="ends_at" type="datetime-local" /></label>
          <label><span>Texto del botón</span><input defaultValue={values.cta_label} name="cta_label" /></label>
          <label><span>Destino del botón</span><input defaultValue={values.cta_url} name="cta_url" placeholder="/catalogo" /></label>
        </div>
      </section>
      <section className="management-form-section">
        <h2>Imágenes y encuadre</h2>
        <p>El ancho siempre ocupa la pantalla. Definí la altura y el punto que debe permanecer visible.</p>
        <div className="management-field-grid">
          <label><span>Imagen para escritorio</span><input accept="image/*" name="desktop_image" type="file" /></label>
          <label><span>Imagen para móvil</span><input accept="image/*" name="mobile_image" type="file" /></label>
          <label className="field-wide"><span>Texto alternativo</span><input defaultValue={values.alt_text} name="alt_text" /></label>
          <label><span>Punto focal horizontal (%)</span><input defaultValue={values.focal_x} max="100" min="0" name="focal_x" type="number" /></label>
          <label><span>Punto focal vertical (%)</span><input defaultValue={values.focal_y} max="100" min="0" name="focal_y" type="number" /></label>
          <label><span>Altura móvil (px)</span><input defaultValue={values.safe_height_mobile} max="1200" min="120" name="safe_height_mobile" type="number" /></label>
          <label><span>Altura tablet (px)</span><input defaultValue={values.safe_height_tablet} max="1200" min="120" name="safe_height_tablet" type="number" /></label>
          <label><span>Altura escritorio (px)</span><input defaultValue={values.safe_height_desktop} max="1200" min="120" name="safe_height_desktop" type="number" /></label>
        </div>
      </section>
      {(kind === "hero" || kind === "promotions") && <section className="management-form-section"><h2>Carrusel</h2><div className="management-field-grid"><label><span>Duración de la diapositiva (ms)</span><input defaultValue={values.interval_ms ?? 6000} min="1000" name="interval_ms" type="number" /></label><label className="management-check"><input defaultChecked={values.pause_on_reduced_motion ?? true} name="pause_on_reduced_motion" type="checkbox" /><span>Detener movimiento reducido</span></label></div></section>}
      {kind === "collections" && <section className="management-form-section"><h2>Productos</h2><label><span>IDs de productos separados por coma</span><input defaultValue={values.product_ids?.join(", ") ?? ""} name="product_ids" /></label></section>}
      {kind === "popups" && <section className="management-form-section"><h2>Comportamiento del aviso</h2><div className="management-field-grid"><label><span>Frecuencia</span><select defaultValue={values.frequency ?? "once_session"} name="frequency"><option value="once_session">Una vez por sesión</option><option value="daily">Una vez por día</option><option value="weekly">Una vez por semana</option><option value="always">Siempre</option></select></label><label><span>Demora antes de mostrar (ms)</span><input defaultValue={values.display_delay_ms ?? 1500} min="0" name="display_delay_ms" type="number" /></label><label><span>Versión de campaña</span><input defaultValue={values.version ?? 1} min="1" name="version" type="number" /></label><label className="management-check"><input defaultChecked={values.dismissible ?? true} name="dismissible" type="checkbox" /><span>Permitir cerrar</span></label></div></section>}
      {state === "saved" && <p className="success-message">Contenido guardado.</p>}
      {state === "error" && <p className="inline-error">No pudimos guardar el contenido.</p>}
      <button className="button primary" disabled={state === "saving"} type="submit">Guardar contenido</button>
    </form>
  );
}
