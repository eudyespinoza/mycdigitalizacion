"use client";

import { useRouter } from "next/navigation";

import { PromotionEditor } from "@/components/management/promotion-editor";
import { managementRequest } from "@/lib/management/api";
import type { ManagedCoupon, ManagedPromotionRule } from "@/lib/management/content-types";


export function PromotionManagementPanel({ rules, coupons }: { rules: ManagedPromotionRule[]; coupons: ManagedCoupon[] }) {
  const router = useRouter();
  const save = async (path: string, payload: Record<string, unknown>) => {
    await managementRequest(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    router.refresh();
  };
  return <div className="promotion-management-grid"><section><div className="management-form-section"><p className="management-kicker">Automáticas</p><h2>Ofertas activas</h2>{rules.length ? <ul className="management-simple-list">{rules.map((rule) => <li key={rule.id}><strong>{rule.name}</strong><span>{rule.value}{rule.discount_type === "percentage" ? "%" : " ARS"} · {rule.enabled ? "habilitada" : "pausada"}</span></li>)}</ul> : <p>No hay ofertas automáticas.</p>}</div><PromotionEditor kind="rule" onSave={(payload) => save("/promotions/rules/", payload)} /></section><section><div className="management-form-section"><p className="management-kicker">Códigos</p><h2>Cupones</h2>{coupons.length ? <ul className="management-simple-list">{coupons.map((coupon) => <li key={coupon.id}><strong>{coupon.code}</strong><span>{coupon.value}{coupon.discount_type === "percentage" ? "%" : " ARS"} · {coupon.enabled ? "habilitado" : "pausado"}</span></li>)}</ul> : <p>No hay cupones.</p>}</div><PromotionEditor kind="coupon" onSave={(payload) => save("/promotions/coupons/", payload)} /></section></div>;
}
