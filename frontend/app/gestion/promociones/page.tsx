import { PromotionManagementPanel } from "@/components/management/promotion-management-panel";
import type { ManagedCoupon, ManagedPromotionRule } from "@/lib/management/content-types";
import { managementServerGet } from "@/lib/management/server-api";


export default async function ManagementPromotionsPage() {
  const [rules, coupons] = await Promise.all([
    managementServerGet<{ results: ManagedPromotionRule[] }>("/promotions/rules/"),
    managementServerGet<{ results: ManagedCoupon[] }>("/promotions/coupons/"),
  ]);
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Comercial</p><h1>Promociones y cupones</h1><p>Programá descuentos automáticos o códigos, con vigencia y reglas de combinación.</p></div></header><div className="management-content-gap"><PromotionManagementPanel coupons={coupons.results} rules={rules.results} /></div></div>;
}
