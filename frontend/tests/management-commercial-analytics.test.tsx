import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { CommercialAnalyticsDashboard } from "@/components/management/analytics/commercial-analytics-dashboard";
import type { AnalyticsFilters, CommercialAnalyticsReport } from "@/lib/management/analytics-types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/gestion/estadisticas",
  useRouter: () => ({ replace: vi.fn() }),
}));

const filters: AnalyticsFilters = {
  from: "2026-08-01",
  to: "2026-09-01",
  compare: false,
  coverageDays: 30,
  category: null,
  brand: null,
};

const report: CommercialAnalyticsReport = {
  period: { from: filters.from, to: filters.to, timezone: "America/Argentina/Buenos_Aires" },
  data_since: "2026-08-01T00:00:00Z",
  filters: { category: null, brand: null, coverage_days: 30 },
  coverage: { attribution_percentage: "91.2", cost_percentage: "76.5" },
  kpis: {
    net_sales: "150000.00",
    paid_orders: 12,
    net_units: "27.00",
    average_ticket: "12500.00",
    discounts: "8500.00",
    refunds: "10000.00",
    gross_product_margin: "47000.00",
    inventory_value: "820000.00",
    reorder_variants: 1,
  },
  series: [{ date: "2026-08-01", sales: "45000.00", refunds: "5000.00", net_sales: "40000.00" }],
  tables: {
    skus: [{
      sku: "LIB-A5-RAY",
      product_id: 7,
      product: "Cuaderno A5",
      category: "Librería",
      units: "8.00",
      revenue: "64000.00",
      margin: "23000.00",
      cost_covered: true,
    }],
    reorder: [{
      variant_id: 22,
      sku: "LIB-A5-RAY",
      product: "Cuaderno A5",
      stock: 2,
      sold_units: "8.00",
      daily_velocity: "0.27",
      stock_coverage_days: "7.5",
      suggested_units: 6,
    }],
    no_movement: [],
  },
  comparison: null,
};

describe("estadísticas de compras y ventas", () => {
  test("expone ventas netas, costo cubierto y una reposición explicable", () => {
    render(
      <CommercialAnalyticsDashboard
        brands={[{ id: 2, name: "Pulso" }]}
        categories={[{ id: 1, name: "Librería" }]}
        filters={filters}
        report={report}
      />,
    );

    expect(screen.getByRole("heading", { name: "Compras y ventas" })).toBeVisible();
    expect(document.querySelector(".analytics-kpi-grid.is-commercial")).toBeInTheDocument();
    expect(screen.getByText("Cobertura de costos 76,5 %")).toBeVisible();
    expect(screen.getByRole("table", { name: "Reposición sugerida" })).toBeVisible();
    expect(screen.getByText(/No contempla proveedor ni lote mínimo/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute(
      "href",
      "/api/v1/management/analytics/commercial/export.csv?from=2026-08-01&to=2026-09-01&coverage_days=30",
    );
  });
});
