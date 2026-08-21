"use client";

import { FormEvent, useMemo, useState } from "react";

import type { PromotionScopeOption } from "@/lib/management/content-types";


type PromotionPayload = Record<string, string | number | boolean | number[] | null>;

type PromotionEditorProps = {
  kind: "rule" | "coupon";
  onSave: (payload: PromotionPayload) => Promise<void>;
  productOptions?: PromotionScopeOption[];
  categoryOptions?: PromotionScopeOption[];
};

function ScopePicker({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: PromotionScopeOption[];
  selected: number[];
  onChange: (selected: number[]) => void;
}) {
  const [query, setQuery] = useState("");
  const visibleOptions = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("es-AR");
    if (!normalized) return options;
    return options.filter((option) => (
      `${option.label} ${option.description ?? ""}`.toLocaleLowerCase("es-AR").includes(normalized)
    ));
  }, [options, query]);

  return (
    <fieldset className="promotion-scope-picker field-wide">
      <legend>{label}</legend>
      <label>
        <span>Buscar</span>
        <input
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`Buscar en ${label.toLocaleLowerCase("es-AR")}`}
          type="search"
          value={query}
        />
      </label>
      <div className="promotion-scope-options">
        {visibleOptions.length ? visibleOptions.map((option) => (
          <label className="promotion-scope-option" key={option.id}>
            <input
              checked={selected.includes(option.id)}
              onChange={(event) => onChange(
                event.target.checked
                  ? [...selected, option.id]
                  : selected.filter((id) => id !== option.id),
              )}
              type="checkbox"
            />
            <span>
              <strong>{option.label}</strong>
              {option.description ? <small>{option.description}</small> : null}
            </span>
          </label>
        )) : <p>No hay coincidencias.</p>}
      </div>
    </fieldset>
  );
}

export function PromotionEditor({
  kind,
  onSave,
  productOptions = [],
  categoryOptions = [],
}: PromotionEditorProps) {
  const [feedback, setFeedback] = useState("");
  const [saving, setSaving] = useState(false);
  const [productIds, setProductIds] = useState<number[]>([]);
  const [categoryIds, setCategoryIds] = useState<number[]>([]);
  const now = new Date();
  const nextWeek = new Date(now.getTime() + 7 * 86400000);
  const local = (date: Date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const maximum = String(form.get("max_redemptions") ?? "").trim();
    const payload: PromotionPayload = {
      ...(kind === "coupon" ? { code: String(form.get("code")) } : { name: String(form.get("name")) }),
      discount_type: String(form.get("discount_type")),
      value: String(form.get("value")),
      starts_at: String(form.get("starts_at")),
      ends_at: String(form.get("ends_at")),
      enabled: form.has("enabled"),
      ...(kind === "coupon" ? {
        combinable: form.has("combinable"),
        max_redemptions: maximum ? Number(maximum) : null,
      } : {
        product_ids: productIds,
        category_ids: categoryIds,
      }),
    };
    setSaving(true);
    setFeedback("");
    try {
      await onSave(payload);
      formElement.reset();
      setProductIds([]);
      setCategoryIds([]);
      setFeedback("Promoción guardada. Podés cargar otra.");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "No pudimos guardar la promoción.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <section className="management-form-section">
        <h2>{kind === "coupon" ? "Nuevo cupón" : "Nueva oferta automática"}</h2>
        <div className="management-field-grid">
          {kind === "coupon" ? (
            <label><span>Código</span><input name="code" required /></label>
          ) : (
            <label><span>Nombre interno</span><input name="name" required /></label>
          )}
          <label>
            <span>Tipo de descuento</span>
            <select defaultValue="percentage" name="discount_type">
              <option value="percentage">Porcentaje</option>
              <option value="fixed">Monto fijo</option>
            </select>
          </label>
          <label><span>Valor</span><input min="0.01" name="value" required step="0.01" type="number" /></label>
          <label><span>Comienza</span><input defaultValue={local(now)} name="starts_at" required type="datetime-local" /></label>
          <label><span>Finaliza</span><input defaultValue={local(nextWeek)} name="ends_at" required type="datetime-local" /></label>
          <label className="management-check"><input defaultChecked name="enabled" type="checkbox" /><span>Habilitada</span></label>
          {kind === "coupon" ? (
            <>
              <label>
                <span>Cantidad máxima de usos</span>
                <input min="1" name="max_redemptions" placeholder="Sin límite" type="number" />
              </label>
              <label className="management-check"><input name="combinable" type="checkbox" /><span>Combinable con ofertas</span></label>
            </>
          ) : (
            <>
              <ScopePicker label="Productos incluidos" onChange={setProductIds} options={productOptions} selected={productIds} />
              <ScopePicker label="Categorías incluidas" onChange={setCategoryIds} options={categoryOptions} selected={categoryIds} />
            </>
          )}
        </div>
      </section>
      {feedback ? <p className={feedback.startsWith("Promoción guardada") ? "success-message" : "inline-error"}>{feedback}</p> : null}
      <button className="button primary" disabled={saving} type="submit">
        {saving ? "Guardando..." : `Guardar ${kind === "coupon" ? "cupón" : "oferta"}`}
      </button>
    </form>
  );
}
