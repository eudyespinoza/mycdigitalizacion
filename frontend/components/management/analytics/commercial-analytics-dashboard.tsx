import Link from "next/link";

import { AnalyticsDataTable } from "@/components/management/analytics/data-table";
import { AnalyticsFilters } from "@/components/management/analytics/analytics-filters";
import { KpiGrid } from "@/components/management/analytics/kpi-grid";
import { MetricChart } from "@/components/management/analytics/metric-chart";
import { buildAnalyticsQuery } from "@/lib/management/analytics-filters";
import type { AnalyticsFilters as FilterValues, CommercialAnalyticsReport } from "@/lib/management/analytics-types";

type FilterOption = { id: number; name: string };

const money = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });

function percent(value: string | null) {
  return value === null ? "Sin datos" : `${number.format(Number(value))} %`;
}

export function CommercialAnalyticsDashboard({
  report,
  filters,
  categories,
  brands,
}: {
  report: CommercialAnalyticsReport;
  filters: FilterValues;
  categories: FilterOption[];
  brands: FilterOption[];
}) {
  const skuRows = report.tables.skus.map((row) => ({ ...row, id: row.sku }));
  const reorderRows = report.tables.reorder.map((row) => ({ ...row, id: row.variant_id }));
  const noMovementRows = report.tables.no_movement.map((row) => ({ ...row, id: row.variant_id }));
  const categoryRows = Array.from(report.tables.skus.reduce((totals, row) => {
    const current = totals.get(row.category) ?? { category: row.category || "Sin categoría", units: 0, revenue: 0, margin: 0 };
    current.units += Number(row.units);
    current.revenue += Number(row.revenue);
    current.margin += Number(row.margin);
    totals.set(current.category, current);
    return totals;
  }, new Map<string, { category: string; units: number; revenue: number; margin: number }>()).values())
    .map((row) => ({ ...row, id: row.category }));
  const exportHref = `/api/v1/management/analytics/commercial/export.csv?${buildAnalyticsQuery(filters)}`;

  return (
    <div className="management-page analytics-page">
      <header className="management-page-header analytics-page-header">
        <div>
          <h1>Compras y ventas</h1>
          <p>Rentabilidad, rotación y reposición para decidir con datos del comercio.</p>
        </div>
        <a className="button secondary" href={exportHref}>Exportar CSV</a>
      </header>
      <AnalyticsFilters brands={brands} categories={categories} commercial filters={filters} />
      <KpiGrid items={[
        { label: "Ventas netas", value: report.kpis.net_sales, kind: "money" },
        { label: "Pedidos pagos", value: report.kpis.paid_orders },
        { label: "Unidades netas", value: report.kpis.net_units },
        { label: "Ticket promedio", value: report.kpis.average_ticket, kind: "money", hasDenominator: report.kpis.average_ticket !== null },
        { label: "Descuentos", value: report.kpis.discounts, kind: "money" },
        { label: "Reembolsos", value: report.kpis.refunds, kind: "money" },
        { label: "Margen bruto de producto", value: report.kpis.gross_product_margin, kind: "money", detail: "No incluye impuestos, envío ni costos operativos." },
        { label: "Valor de inventario", value: report.kpis.inventory_value, kind: "money", detail: "Según costo cargado." },
        { label: "Variantes a reponer", value: report.kpis.reorder_variants },
      ]} />
      <p className="analytics-coverage-note">
        <span>Cobertura de costos {percent(report.coverage.cost_percentage)}</span>
        <small>El margen muestra solo artículos con costo conocido; no se estima lo faltante.</small>
      </p>
      <MetricChart
        title="Ventas y devoluciones"
        points={report.series}
        series={[
          { key: "sales", label: "Ventas" },
          { key: "refunds", label: "Devoluciones" },
          { key: "net_sales", label: "Venta neta" },
        ]}
      />
      <div className="analytics-two-column">
        <section className="analytics-section">
          <div className="analytics-section-heading"><h2>Rendimiento por categoría</h2><p>Unidades, venta y margen de producto.</p></div>
          <AnalyticsDataTable
            caption="Rendimiento por categoría"
            empty="No hubo categorías vendidas en este período."
            rows={categoryRows}
            columns={[
              { key: "category", label: "Categoría" },
              { key: "units", label: "Unidades", align: "numeric", render: (row) => number.format(row.units) },
              { key: "revenue", label: "Venta", align: "numeric", render: (row) => money.format(row.revenue) },
              { key: "margin", label: "Margen", align: "numeric", render: (row) => money.format(row.margin) },
            ]}
          />
        </section>
        <section className="analytics-section">
          <div className="analytics-section-heading"><h2>Sin movimiento</h2><p>Stock sin ventas dentro del período.</p></div>
          <AnalyticsDataTable
            caption="Variantes sin movimiento"
            empty="No hay variantes con stock inmovilizado para estos filtros."
            rows={noMovementRows}
            columns={[
              { key: "sku", label: "SKU" },
              { key: "product", label: "Producto" },
              { key: "stock", label: "Stock", align: "numeric" },
            ]}
          />
        </section>
      </div>
      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Productos y SKU</h2><p>Detalle comercial con cobertura de costo visible.</p></div>
        <AnalyticsDataTable
          caption="Rendimiento por SKU"
          empty="No hubo ventas de productos en este período."
          rows={skuRows}
          columns={[
            { key: "sku", label: "SKU" },
            { key: "product", label: "Producto", render: (row) => row.product_id ? <Link href={`/gestion/catalogo/${row.product_id}`}>{row.product}</Link> : row.product },
            { key: "category", label: "Categoría" },
            { key: "units", label: "Unidades", align: "numeric", render: (row) => number.format(Number(row.units)) },
            { key: "revenue", label: "Venta", align: "numeric", render: (row) => money.format(Number(row.revenue)) },
            { key: "margin", label: "Margen", align: "numeric", render: (row) => row.cost_covered ? money.format(Number(row.margin)) : "Costo faltante" },
          ]}
        />
      </section>
      <section className="analytics-section analytics-decision-section">
        <div className="analytics-section-heading"><h2>Reposición sugerida</h2><p>Proyección por velocidad de venta y cobertura elegida.</p></div>
        <p className="analytics-decision-note">No contempla proveedor ni lote mínimo: revisá esas condiciones antes de comprar.</p>
        <AnalyticsDataTable
          caption="Reposición sugerida"
          empty="No hay reposiciones sugeridas para estos filtros."
          rows={reorderRows}
          columns={[
            { key: "sku", label: "SKU" },
            { key: "product", label: "Producto" },
            { key: "stock", label: "Stock", align: "numeric" },
            { key: "sold_units", label: "Vendidas", align: "numeric", render: (row) => number.format(Number(row.sold_units)) },
            { key: "daily_velocity", label: "Por día", align: "numeric", render: (row) => number.format(Number(row.daily_velocity)) },
            { key: "stock_coverage_days", label: "Cobertura", align: "numeric", render: (row) => row.stock_coverage_days === null ? "Infinita" : `${number.format(Number(row.stock_coverage_days))} días` },
            { key: "suggested_units", label: "Sugeridas", align: "numeric" },
          ]}
        />
      </section>
    </div>
  );
}
