"use client";

import { FormEvent, useState } from "react";


type PromotionPayload = Record<string, string | number | boolean | number[]>;


export function PromotionEditor({ kind, onSave }: { kind: "rule" | "coupon"; onSave: (payload: PromotionPayload) => Promise<void> }) {
  const [state, setState] = useState("idle");
  const now = new Date();
  const nextWeek = new Date(now.getTime() + 7 * 86400000);
  const local = (date: Date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: PromotionPayload = {
      ...(kind === "coupon" ? { code: String(form.get("code")) } : { name: String(form.get("name")) }),
      discount_type: String(form.get("discount_type")),
      value: String(form.get("value")),
      starts_at: String(form.get("starts_at")),
      ends_at: String(form.get("ends_at")),
      enabled: form.has("enabled"),
      ...(kind === "coupon" ? { combinable: form.has("combinable") } : {
        product_ids: String(form.get("product_ids") ?? "").split(",").map(Number).filter(Boolean),
        category_ids: String(form.get("category_ids") ?? "").split(",").map(Number).filter(Boolean),
      }),
    };
    setState("saving");
    try { await onSave(payload); setState("saved"); } catch { setState("error"); }
  };
  return <form className="management-form" onSubmit={(event) => void submit(event)}><section className="management-form-section"><h2>{kind === "coupon" ? "Nuevo cupón" : "Nueva oferta automática"}</h2><div className="management-field-grid">{kind === "coupon" ? <label><span>Código</span><input name="code" required /></label> : <label><span>Nombre interno</span><input name="name" required /></label>}<label><span>Tipo de descuento</span><select defaultValue="percentage" name="discount_type"><option value="percentage">Porcentaje</option><option value="fixed">Monto fijo</option></select></label><label><span>Valor</span><input min="0.01" name="value" required step="0.01" type="number" /></label><label><span>Comienza</span><input defaultValue={local(now)} name="starts_at" required type="datetime-local" /></label><label><span>Finaliza</span><input defaultValue={local(nextWeek)} name="ends_at" required type="datetime-local" /></label><label className="management-check"><input defaultChecked name="enabled" type="checkbox" /><span>Habilitada</span></label>{kind === "coupon" ? <label className="management-check"><input name="combinable" type="checkbox" /><span>Combinable con ofertas</span></label> : <><label><span>IDs de productos</span><input name="product_ids" placeholder="12, 18" /></label><label><span>IDs de categorías</span><input name="category_ids" placeholder="2, 5" /></label></>}</div></section>{state === "saved" && <p className="success-message">Promoción guardada.</p>}{state === "error" && <p className="inline-error">No pudimos guardar la promoción.</p>}<button className="button primary" type="submit">Guardar {kind === "coupon" ? "cupón" : "oferta"}</button></form>;
}
