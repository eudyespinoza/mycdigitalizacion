"use client";

import { useRouter } from "next/navigation";

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
  const router = useRouter();
  const save = async (path: string, payload: Record<string, unknown>) => {
    await managementRequest(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    router.refresh();
  };
  return (
    <div className="promotion-management-grid">
      <section>
        <div className="management-form-section">
          <p className="management-kicker">Automáticas</p>
          <h2>Ofertas</h2>
          {rules.length ? (
            <ul className="management-simple-list">
              {rules.map((rule) => (
                <li key={rule.id}>
                  <strong>{rule.name}</strong>
                  <span>{rule.value}{rule.discount_type === "percentage" ? "%" : " ARS"} · {rule.enabled ? "habilitada" : "pausada"}</span>
                </li>
              ))}
            </ul>
          ) : <p>No hay ofertas automáticas.</p>}
        </div>
        <PromotionEditor
          categoryOptions={categoryOptions}
          kind="rule"
          onSave={(payload) => save("/promotions/rules/", payload)}
          productOptions={productOptions}
        />
      </section>
      <section>
        <div className="management-form-section">
          <p className="management-kicker">Códigos</p>
          <h2>Cupones</h2>
          {coupons.length ? (
            <ul className="management-simple-list">
              {coupons.map((coupon) => (
                <li key={coupon.id}>
                  <span><strong>{coupon.code}</strong><small>{couponUsage(coupon)}</small></span>
                  <span>{coupon.value}{coupon.discount_type === "percentage" ? "%" : " ARS"} · {coupon.enabled ? "habilitado" : "pausado"}</span>
                </li>
              ))}
            </ul>
          ) : <p>No hay cupones.</p>}
        </div>
        <PromotionEditor kind="coupon" onSave={(payload) => save("/promotions/coupons/", payload)} />
      </section>
    </div>
  );
}
