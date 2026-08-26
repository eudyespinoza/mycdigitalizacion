import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { AnalyticsDataTable } from "@/components/management/analytics/data-table";
import { Funnel } from "@/components/management/analytics/funnel";
import { KpiGrid } from "@/components/management/analytics/kpi-grid";
import { MetricChart } from "@/components/management/analytics/metric-chart";
import { buildAnalyticsQuery, parseAnalyticsFilters } from "@/lib/management/analytics-filters";

test("muestra Sin datos cuando una tasa no tiene denominador", () => {
  render(
    <KpiGrid
      items={[
        {
          label: "Conversión",
          value: null,
          hasDenominator: false,
          kind: "percentage",
        },
      ]}
    />,
  );

  expect(screen.getByText("Sin datos")).toBeVisible();
});

test("mantiene todos los filtros en la URL", () => {
  expect(
    buildAnalyticsQuery({
      from: "2026-08-01",
      to: "2026-09-01",
      compare: true,
      coverageDays: 30,
      category: 3,
      brand: null,
    }),
  ).toBe(
    "from=2026-08-01&to=2026-09-01&compare=1&coverage_days=30&category=3",
  );
  expect(
    parseAnalyticsFilters({ from: "2026-08-10", to: "2026-08-20", coverage_days: "60" }),
  ).toMatchObject({ from: "2026-08-10", to: "2026-08-20", coverageDays: 60 });
});

test("el gráfico conserva una tabla accesible equivalente", () => {
  render(
    <MetricChart
      title="Actividad diaria"
      series={[{ key: "sessions", label: "Sesiones" }]}
      points={[
        { date: "2026-08-01", sessions: 10 },
        { date: "2026-08-02", sessions: 15 },
      ]}
    />,
  );

  expect(screen.getByRole("img", { name: "Actividad diaria" })).toBeVisible();
  expect(screen.getByRole("table", { name: "Datos de Actividad diaria" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "15" })).toBeVisible();
});

test("el embudo y la tabla operativa usan encabezados explícitos", () => {
  const { rerender } = render(
    <Funnel
      title="Embudo de compra"
      steps={[
        { label: "Sesiones", count: 100, rate: "100.00", hasDenominator: true },
        { label: "Carrito", count: 20, rate: "20.00", hasDenominator: true },
      ]}
    />,
  );
  expect(screen.getByRole("heading", { name: "Embudo de compra" })).toBeVisible();
  expect(screen.getByText("20,0 %")).toBeVisible();

  rerender(
    <AnalyticsDataTable
      caption="Productos"
      columns={[
        { key: "name", label: "Producto" },
        { key: "views", label: "Vistas", align: "numeric" },
      ]}
      rows={[{ id: 1, name: "Cuaderno", views: 12 }]}
    />,
  );
  expect(screen.getByRole("columnheader", { name: "Producto" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "Cuaderno" })).toBeVisible();
});
