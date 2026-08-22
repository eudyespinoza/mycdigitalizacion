"use client";

import { FormEvent, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import type { ShippingBox } from "@/lib/management/operations-types";


type BoxPayload = Omit<ShippingBox, "id">;


export function ShippingBoxPanel({ boxes, onCreate }: { boxes: ShippingBox[]; onCreate: (payload: BoxPayload) => Promise<ShippingBox | void> }) {
  const [rows, setRows] = useState(boxes);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload: BoxPayload = {
      code: String(data.get("code")),
      inner_length_cm: String(data.get("inner_length_cm")),
      inner_width_cm: String(data.get("inner_width_cm")),
      inner_height_cm: String(data.get("inner_height_cm")),
      tare_weight_grams: Number(data.get("tare_weight_grams")),
      max_weight_grams: Number(data.get("max_weight_grams")),
      enabled: true,
    };
    setSaving(true);
    setError("");
    try {
      const created = await onCreate(payload);
      if (created) setRows((current) => [...current, created]);
      setOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos guardar el embalaje.");
    } finally {
      setSaving(false);
    }
  };
  return (
    <div>
      <section className="management-form-section">
        <div className="management-section-heading">
          <div><h2>Embalajes disponibles</h2><p>Medidas internas y peso máximo utilizados para cotizar.</p></div>
          <button className="button primary" onClick={() => { setError(""); setOpen(true); }} type="button">Agregar embalaje</button>
        </div>
        {rows.length ? <ul className="management-simple-list">{rows.map((box) => <li key={box.id}><strong>{box.code}</strong><span>{box.inner_length_cm} × {box.inner_width_cm} × {box.inner_height_cm} cm · hasta {box.max_weight_grams} g</span></li>)}</ul> : <p>Todavía no cargaste embalajes.</p>}
      </section>
      <ManagementFormDialog
        description="Cargá las medidas interiores para que el cálculo de bultos sea preciso."
        onClose={() => { if (!saving) setOpen(false); }}
        open={open}
        title="Nuevo embalaje"
      >
        <form className="compact-management-form" onSubmit={(event) => void submit(event)}>
          <label><span>Código</span><input name="code" required /></label>
          <div className="management-field-grid">
            <label><span>Largo interior (cm)</span><input min="0.01" name="inner_length_cm" required step="0.01" type="number" /></label>
            <label><span>Ancho interior (cm)</span><input min="0.01" name="inner_width_cm" required step="0.01" type="number" /></label>
            <label><span>Alto interior (cm)</span><input min="0.01" name="inner_height_cm" required step="0.01" type="number" /></label>
            <label><span>Tara (g)</span><input min="0" name="tare_weight_grams" required type="number" /></label>
            <label><span>Peso máximo (g)</span><input min="1" name="max_weight_grams" required type="number" /></label>
          </div>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions">
            <button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar embalaje"}</button>
            <button className="button secondary" disabled={saving} onClick={() => setOpen(false)} type="button">Cancelar</button>
          </div>
        </form>
      </ManagementFormDialog>
    </div>
  );
}
