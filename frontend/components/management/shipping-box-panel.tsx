"use client";

import { FormEvent, useState } from "react";

import type { ShippingBox } from "@/lib/management/operations-types";


type BoxPayload = Omit<ShippingBox, "id">;


export function ShippingBoxPanel({ boxes, onCreate }: { boxes: ShippingBox[]; onCreate: (payload: BoxPayload) => Promise<void> }) {
  const [rows] = useState(boxes);
  const [message, setMessage] = useState("");
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
    await onCreate(payload);
    setMessage("Embalaje guardado. Actualizá la página para verlo en la lista.");
    form.reset();
  };
  return (
    <div className="management-detail-grid">
      <section className="management-form-section">
        <h2>Embalajes disponibles</h2>
        {rows.length ? <ul className="management-simple-list">{rows.map((box) => <li key={box.id}><strong>{box.code}</strong><span>{box.inner_length_cm} × {box.inner_width_cm} × {box.inner_height_cm} cm · hasta {box.max_weight_grams} g</span></li>)}</ul> : <p>Todavía no cargaste embalajes.</p>}
      </section>
      <form className="management-form-section compact-management-form" onSubmit={(event) => void submit(event)}>
        <h2>Nuevo embalaje</h2>
        <label><span>Código</span><input name="code" required /></label>
        <div className="management-field-grid">
          <label><span>Largo interior (cm)</span><input min="0.01" name="inner_length_cm" required step="0.01" type="number" /></label>
          <label><span>Ancho interior (cm)</span><input min="0.01" name="inner_width_cm" required step="0.01" type="number" /></label>
          <label><span>Alto interior (cm)</span><input min="0.01" name="inner_height_cm" required step="0.01" type="number" /></label>
          <label><span>Tara (g)</span><input min="0" name="tare_weight_grams" required type="number" /></label>
          <label><span>Peso máximo (g)</span><input min="1" name="max_weight_grams" required type="number" /></label>
        </div>
        <button className="button primary" type="submit">Guardar embalaje</button>
        {message && <p className="management-notice" role="status">{message}</p>}
      </form>
    </div>
  );
}
