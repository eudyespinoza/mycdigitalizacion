import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { WebAnalyticsDashboard } from "@/components/management/analytics/web-analytics-dashboard";
import type { AnalyticsFilters, WebAnalyticsReport } from "@/lib/management/analytics-types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/gestion/metricas",
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

const report: WebAnalyticsReport = {
  period: { from: filters.from, to: filters.to, timezone: "America/Argentina/Buenos_Aires" },
  data_since: "2026-08-01T10:00:00-03:00",
  coverage: { attribution_percentage: "93.40", has_denominator: true },
  kpis: {
    sessions: 120,
    visitors: 95,
    conversion_rate: "3.50",
    attributed_revenue: "87500.00",
    average_ticket: "21875.00",
    checkout_abandonment: "28.00",
  },
  funnel: {
    sessions: { count: 120, rate: "100.00", has_denominator: true },
    product: { count: 80, rate: "66.67", has_denominator: true },
    cart: { count: 30, rate: "37.50", has_denominator: true },
    checkout: { count: 12, rate: "40.00", has_denominator: true },
    delivery: { count: 10, rate: "83.33", has_denominator: true },
    payment: { count: 8, rate: "66.67", has_denominator: true },
    paid: { count: 4, rate: "50.00", has_denominator: true },
  },
  series: [{ date: "2026-08-01", sessions: 12, carts: 3, orders: 1 }],
  tables: {
    products: [{ product_id: 7, name: "Cuaderno A5", views: 30, cart_additions: 8, cart_rate: "26.67" }],
    channels: [{ source: "instagram", medium: "social", campaign: "agosto", sessions: 60, conversion_rate: "5.00", revenue: "50000.00" }],
    devices: [{ device: "mobile", sessions: 80, conversion_rate: "4.00", revenue: "60000.00" }],
  },
  comparison: null,
};

test("renderiza embudo, cobertura y rendimiento sin ocultar la fuente", () => {
  render(<WebAnalyticsDashboard filters={filters} report={report} />);

  expect(screen.getByRole("heading", { name: "Métricas de la tienda" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Embudo de compra" })).toBeVisible();
  expect(screen.getByText("Cobertura de atribución 93,4 %")).toBeVisible();
  expect(screen.getByRole("link", { name: "Cuaderno A5" })).toHaveAttribute("href", "/gestion/catalogo/7");
  expect(screen.getByRole("table", { name: "Canales" })).toBeVisible();
});

test("explica cuándo empezó la medición sin inventar ceros históricos", () => {
  const empty = {
    ...report,
    kpis: { ...report.kpis, sessions: 0, visitors: 0, conversion_rate: null },
    tables: { products: [], channels: [], devices: [] },
  };
  render(<WebAnalyticsDashboard filters={filters} report={empty} />);

  expect(screen.getByText(/la medición comenzó el 1 de agosto de 2026/i)).toBeVisible();
  expect(screen.getByText("Sin datos en este período.")).toBeVisible();
});
