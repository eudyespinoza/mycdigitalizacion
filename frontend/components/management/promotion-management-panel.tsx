"use client";

import { useState } from "react";

import { PromotionEditor } from "@/components/management/promotion-editor";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { managementRequest } from "@/lib/management/api";
import type {
  ManagedCoupon,
  ManagedPromotionRule,
  PromotionScopeOption,
} from "@/lib/management/content-types";


type PromotionManagementPanelProps = {
  rules: ManagedPromotionRule[];
  coupons: ManagedCoupon[];
  productOptions?: PromotionScopeOption[];
  categoryOptions?: PromotionScopeOption[];
};

type PromotionEditorState =
  | { kind: "rule"; value?: ManagedPromotionRule }
  | { kind: "coupon"; value?: ManagedCoupon };

type PromotionDeleteTarget =
  | { kind: "rule"; id: number; label: string }
  | { kind: "coupon"; id: number; label: string };

function couponUsage(coupon: ManagedCoupon) {
  if (coupon.max_redemptions === null) {
    return `${coupon.used_redemptions} usos, sin límite`;
  }
  return `${coupon.used_redemptions} de ${coupon.max_redemptions} usados`;
}

export function PromotionManagementPanel({
  rules,
  coupons,
  productOptions = [],
  categoryOptions = [],
}: PromotionManagementPanelProps) {
  const [ruleRows, setRuleRows] = useState(rules);
  const [couponRows, setCouponRows] = useState(coupons);
  const [editor, setEditor] = useState<PromotionEditorState | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PromotionDeleteTarget | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState("");

  async function createRule(payload: Record<string, unknown>) {
    const created = await managementRequest<ManagedPromotionRule>("/promotions/rules/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setRuleRows((current) => [created, ...current]);
  }

  async function createCoupon(payload: Record<string, unknown>) {
    const created = await managementRequest<ManagedCoupon>("/promotions/coupons/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setCouponRows((current) => [created, ...current]);
  }

  async function updateRule(rule: ManagedPromotionRule, payload: Record<string, unknown>) {
    const updated = await managementRequest<ManagedPromotionRule>(
      `/promotions/rules/${rule.id}/`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setRuleRows((current) => current.map((row) => row.id === updated.id ? updated : row));
  }

  async function updateCoupon(coupon: ManagedCoupon, payload: Record<string, unknown>) {
    const updated = await managementRequest<ManagedCoupon>(
      `/promotions/coupons/${coupon.id}/`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setCouponRows((current) => current.map((row) => row.id === updated.id ? updated : row));
  }

  async function saveEditor(payload: Record<string, unknown>) {
    if (!editor) return;
    if (editor.kind === "rule") {
      if (editor.value) await updateRule(editor.value, payload);
      else await createRule(payload);
    } else if (editor.value) await updateCoupon(editor.value, payload);
    else await createCoupon(payload);
    setEditor(null);
  }

  async function remove() {
    if (!deleteTarget) return;
    setDeleting(true);
    setActionError("");
    try {
      const resource = deleteTarget.kind === "rule" ? "rules" : "coupons";
      await managementRequest<void>(`/promotions/${resource}/${deleteTarget.id}/`, { method: "DELETE" });
      if (deleteTarget.kind === "rule") {
        setRuleRows((current) => current.filter((row) => row.id !== deleteTarget.id));
      } else {
        setCouponRows((current) => current.filter((row) => row.id !== deleteTarget.id));
      }
      setDeleteTarget(null);
    } catch {
      setActionError("No pudimos eliminar. Intentá nuevamente.");
    } finally {
      setDeleting(false);
    }
  }

  const editorTitle = editor?.kind === "coupon"
    ? editor.value ? "Editar cupón" : "Nuevo cupón"
    : editor?.value ? "Editar oferta automática" : "Nueva oferta automática";

  return (
    <div className="promotion-management-grid">
      <section>
        <div className="management-form-section">
          <div className="management-section-heading">
            <div><h2>Ofertas automáticas</h2><p>Descuentos programados para productos o categorías.</p></div>
            <button className="button primary" onClick={() => setEditor({ kind: "rule" })} type="button">Nueva oferta</button>
          </div>
          {ruleRows.length ? (
            <ul className="management-simple-list">
              {ruleRows.map((rule) => (
                <li key={rule.id}>
                  <span>
                    <strong>{rule.name}</strong>
                    <small>{rule.value}{rule.discount_type === "percentage" ? "%" : " ARS"} · {rule.enabled ? "habilitada" : "pausada"}</small>
                  </span>
                  <div className="management-content-actions">
                    <button aria-label={`Editar ${rule.name}`} className="button secondary" onClick={() => setEditor({ kind: "rule", value: rule })} type="button">Editar</button>
                    <button aria-label={`Eliminar ${rule.name}`} className="button danger" onClick={() => { setActionError(""); setDeleteTarget({ kind: "rule", id: rule.id, label: rule.name }); }} type="button">Eliminar</button>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p>No hay ofertas automáticas.</p>}
        </div>
      </section>
      <section>
        <div className="management-form-section">
          <div className="management-section-heading">
            <div><h2>Cupones</h2><p>Códigos con límites y reglas de combinación.</p></div>
            <button className="button primary" onClick={() => setEditor({ kind: "coupon" })} type="button">Nuevo cupón</button>
          </div>
          {couponRows.length ? (
            <ul className="management-simple-list">
              {couponRows.map((coupon) => (
                <li key={coupon.id}>
                  <span>
                    <strong>{coupon.code}</strong>
                    <small>{couponUsage(coupon)} · {coupon.value}{coupon.discount_type === "percentage" ? "%" : " ARS"} · {coupon.enabled ? "habilitado" : "pausado"}</small>
                  </span>
                  <div className="management-content-actions">
                    <button aria-label={`Editar ${coupon.code}`} className="button secondary" onClick={() => setEditor({ kind: "coupon", value: coupon })} type="button">Editar</button>
                    <button aria-label={`Eliminar ${coupon.code}`} className="button danger" onClick={() => { setActionError(""); setDeleteTarget({ kind: "coupon", id: coupon.id, label: coupon.code }); }} type="button">Eliminar</button>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p>No hay cupones.</p>}
        </div>
      </section>
      {actionError ? <p className="inline-error promotion-action-error" role="alert">{actionError}</p> : null}
      <ManagementFormDialog
        description={editor?.kind === "rule" ? "Definí el descuento, la vigencia y su alcance." : "Definí el código, la vigencia y sus límites de uso."}
        onClose={() => setEditor(null)}
        open={editor !== null}
        size="wide"
        title={editorTitle}
      >
        {editor ? (
          <PromotionEditor
            categoryOptions={categoryOptions}
            initialValue={editor.value}
            key={`${editor.kind}-${editor.value?.id ?? "new"}`}
            kind={editor.kind}
            onCancel={() => setEditor(null)}
            onSave={saveEditor}
            productOptions={productOptions}
            showHeading={false}
          />
        ) : null}
      </ManagementFormDialog>
      <ConfirmationDialog
        busy={deleting}
        busyLabel="Eliminando…"
        confirmLabel="Eliminar"
        description={deleteTarget ? `Vas a eliminar “${deleteTarget.label}”. Esta acción no se puede deshacer.` : ""}
        error={actionError}
        onCancel={() => { if (!deleting) setDeleteTarget(null); setActionError(""); }}
        onConfirm={remove}
        open={deleteTarget !== null}
        title={deleteTarget?.kind === "coupon" ? "Eliminar cupón" : "Eliminar oferta"}
      />
    </div>
  );
}
