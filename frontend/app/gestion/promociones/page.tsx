import { PromotionManagementPanel } from "@/components/management/promotion-management-panel";
import type {
  ManagedCoupon,
  ManagedPromotionRule,
  PromotionScopeOption,
} from "@/lib/management/content-types";
import { managementServerGet } from "@/lib/management/server-api";


export default async function ManagementPromotionsPage() {
  const [rules, coupons, scopeOptions] = await Promise.all([
    managementServerGet<{ results: ManagedPromotionRule[] }>("/promotions/rules/"),
    managementServerGet<{ results: ManagedCoupon[] }>("/promotions/coupons/"),
    managementServerGet<{
      products: PromotionScopeOption[];
      categories: PromotionScopeOption[];
    }>("/promotions/scope-options/"),
  ]);
  return (
    <div className="management-page">
      <header className="management-page-header">
        <div>
          <p className="management-kicker">Comercial</p>
          <h1>Promociones y cupones</h1>
          <p>Programá descuentos, controlá sus alcances y definí límites de uso.</p>
        </div>
      </header>
      <div className="management-content-gap">
        <PromotionManagementPanel
          categoryOptions={scopeOptions.categories}
          coupons={coupons.results}
          productOptions={scopeOptions.products}
          rules={rules.results}
        />
      </div>
    </div>
  );
}
