"use client";

import { FormEvent, useMemo, useState } from "react";

import type {
  ManagedCoupon,
  ManagedPromotionRule,
  PromotionScopeOption,
} from "@/lib/management/content-types";


type PromotionPayload = Record<string, string | number | boolean | number[] | null>;

type PromotionEditorProps = {
  kind: "rule" | "coupon";
  onSave: (payload: PromotionPayload) => Promise<void>;
  initialValue?: ManagedPromotionRule | ManagedCoupon;
  onCancel?: () => void;
  productOptions?: PromotionScopeOption[];
  categoryOptions?: PromotionScopeOption[];
  showHeading?: boolean;
};

function localDateTime(value: Date | string) {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

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
  initialValue,
  onCancel,
  productOptions = [],
  categoryOptions = [],
  showHeading = true,
}: PromotionEditorProps) {
  const [feedback, setFeedback] = useState("");
  const [saving, setSaving] = useState(false);
  const [productIds, setProductIds] = useState<number[]>(
    initialValue && "product_ids" in initialValue ? initialValue.product_ids : [],
  );
  const [categoryIds, setCategoryIds] = useState<number[]>(
    initialValue && "category_ids" in initialValue ? initialValue.category_ids : [],
  );
  const now = new Date();
  const nextWeek = new Date(now.getTime() + 7 * 86400000);
  const editing = Boolean(initialValue);

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
      if (!editing) {
        formElement.reset();
        setProductIds([]);
        setCategoryIds([]);
        setFeedback("Promoción guardada. Podés cargar otra.");
      }
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "No pudimos guardar la promoción.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <section className="management-form-section">
        {showHeading ? <h2>
          {editing
            ? kind === "coupon" ? "Editar cupón" : "Editar oferta automática"
            : kind === "coupon" ? "Nuevo cupón" : "Nueva oferta automática"}
        </h2> : null}
        <div className="management-field-grid">
          {kind === "coupon" ? (
            <label><span>Código</span><input defaultValue={initialValue && "code" in initialValue ? initialValue.code : ""} name="code" required /></label>
          ) : (
            <label><span>Nombre interno</span><input defaultValue={initialValue && "name" in initialValue ? initialValue.name : ""} name="name" required /></label>
          )}
          <label>
            <span>Tipo de descuento</span>
            <select defaultValue={initialValue?.discount_type ?? "percentage"} name="discount_type">
              <option value="percentage">Porcentaje</option>
              <option value="fixed">Monto fijo</option>
            </select>
          </label>
          <label><span>Valor</span><input defaultValue={initialValue?.value ?? ""} min="0.01" name="value" required step="0.01" type="number" /></label>
          <label><span>Comienza</span><input defaultValue={localDateTime(initialValue?.starts_at ?? now)} name="starts_at" required type="datetime-local" /></label>
          <label><span>Finaliza</span><input defaultValue={localDateTime(initialValue?.ends_at ?? nextWeek)} name="ends_at" required type="datetime-local" /></label>
          <label className="management-check"><input defaultChecked={initialValue?.enabled ?? true} name="enabled" type="checkbox" /><span>Habilitada</span></label>
          {kind === "coupon" ? (
            <>
              <label>
                <span>Cantidad máxima de usos</span>
                <input defaultValue={initialValue && "max_redemptions" in initialValue ? initialValue.max_redemptions ?? "" : ""} min="1" name="max_redemptions" placeholder="Sin límite" type="number" />
              </label>
              <label className="management-check"><input defaultChecked={initialValue && "combinable" in initialValue ? initialValue.combinable : false} name="combinable" type="checkbox" /><span>Combinable con ofertas</span></label>
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
      <div className="management-form-actions">
        <button className="button primary" disabled={saving} type="submit">
          {saving
            ? "Guardando..."
            : editing
              ? `Guardar cambios ${kind === "coupon" ? "del cupón" : "de oferta"}`
              : `Guardar ${kind === "coupon" ? "cupón" : "oferta"}`}
        </button>
        {onCancel ? <button className="button secondary" onClick={onCancel} type="button">Cancelar</button> : null}
      </div>
    </form>
  );
}
