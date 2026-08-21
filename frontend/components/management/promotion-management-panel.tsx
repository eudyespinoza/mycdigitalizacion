"use client";

import { useState } from "react";

import { PromotionEditor } from "@/components/management/promotion-editor";
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
  const [editingRule, setEditingRule] = useState<ManagedPromotionRule | null>(null);
  const [editingCoupon, setEditingCoupon] = useState<ManagedCoupon | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
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

  async function updateRule(payload: Record<string, unknown>) {
    if (!editingRule) return;
    const updated = await managementRequest<ManagedPromotionRule>(
      `/promotions/rules/${editingRule.id}/`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setRuleRows((current) => current.map((row) => row.id === updated.id ? updated : row));
    setEditingRule(null);
  }

  async function updateCoupon(payload: Record<string, unknown>) {
    if (!editingCoupon) return;
    const updated = await managementRequest<ManagedCoupon>(
      `/promotions/coupons/${editingCoupon.id}/`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setCouponRows((current) => current.map((row) => row.id === updated.id ? updated : row));
    setEditingCoupon(null);
  }

  async function remove(kind: "rule" | "coupon", id: number, label: string) {
    if (!window.confirm(`¿Eliminar “${label}”? Esta acción no se puede deshacer.`)) return;
    const key = `${kind}:${id}`;
    setDeleting(key);
    setActionError("");
    try {
      const resource = kind === "rule" ? "rules" : "coupons";
      await managementRequest<void>(`/promotions/${resource}/${id}/`, { method: "DELETE" });
      if (kind === "rule") {
        setRuleRows((current) => current.filter((row) => row.id !== id));
        if (editingRule?.id === id) setEditingRule(null);
      } else {
        setCouponRows((current) => current.filter((row) => row.id !== id));
        if (editingCoupon?.id === id) setEditingCoupon(null);
      }
    } catch {
      setActionError("No pudimos eliminar. Intentá nuevamente.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="promotion-management-grid">
      <section>
        <div className="management-form-section">
          <p className="management-kicker">Automáticas</p>
          <h2>Ofertas</h2>
          {ruleRows.length ? (
            <ul className="management-simple-list">
              {ruleRows.map((rule) => (
                <li key={rule.id}>
                  <span>
                    <strong>{rule.name}</strong>
                    <small>{rule.value}{rule.discount_type === "percentage" ? "%" : " ARS"} · {rule.enabled ? "habilitada" : "pausada"}</small>
                  </span>
                  <div className="management-content-actions">
                    <button aria-label={`Editar ${rule.name}`} className="button secondary" onClick={() => setEditingRule(rule)} type="button">Editar</button>
                    <button aria-label={`Eliminar ${rule.name}`} className="button danger" disabled={deleting === `rule:${rule.id}`} onClick={() => void remove("rule", rule.id, rule.name)} type="button">{deleting === `rule:${rule.id}` ? "Eliminando…" : "Eliminar"}</button>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p>No hay ofertas automáticas.</p>}
        </div>
        <PromotionEditor
          categoryOptions={categoryOptions}
          initialValue={editingRule ?? undefined}
          key={editingRule ? `edit-rule-${editingRule.id}` : "new-rule"}
          kind="rule"
          onCancel={editingRule ? () => setEditingRule(null) : undefined}
          onSave={editingRule ? updateRule : createRule}
          productOptions={productOptions}
        />
      </section>
      <section>
        <div className="management-form-section">
          <p className="management-kicker">Códigos</p>
          <h2>Cupones</h2>
          {couponRows.length ? (
            <ul className="management-simple-list">
              {couponRows.map((coupon) => (
                <li key={coupon.id}>
                  <span>
                    <strong>{coupon.code}</strong>
                    <small>{couponUsage(coupon)} · {coupon.value}{coupon.discount_type === "percentage" ? "%" : " ARS"} · {coupon.enabled ? "habilitado" : "pausado"}</small>
                  </span>
                  <div className="management-content-actions">
                    <button aria-label={`Editar ${coupon.code}`} className="button secondary" onClick={() => setEditingCoupon(coupon)} type="button">Editar</button>
                    <button aria-label={`Eliminar ${coupon.code}`} className="button danger" disabled={deleting === `coupon:${coupon.id}`} onClick={() => void remove("coupon", coupon.id, coupon.code)} type="button">{deleting === `coupon:${coupon.id}` ? "Eliminando…" : "Eliminar"}</button>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p>No hay cupones.</p>}
        </div>
        <PromotionEditor
          initialValue={editingCoupon ?? undefined}
          key={editingCoupon ? `edit-coupon-${editingCoupon.id}` : "new-coupon"}
          kind="coupon"
          onCancel={editingCoupon ? () => setEditingCoupon(null) : undefined}
          onSave={editingCoupon ? updateCoupon : createCoupon}
        />
      </section>
      {actionError ? <p className="inline-error promotion-action-error" role="alert">{actionError}</p> : null}
    </div>
  );
}
