import Link from "next/link";

import { AnalyticsDataTable } from "@/components/management/analytics/data-table";
import { AnalyticsFilters } from "@/components/management/analytics/analytics-filters";
import { Funnel } from "@/components/management/analytics/funnel";
import { KpiGrid } from "@/components/management/analytics/kpi-grid";
import { MetricChart } from "@/components/management/analytics/metric-chart";
import type { AnalyticsFilters as FilterValues, WebAnalyticsReport } from "@/lib/management/analytics-types";

const percentage = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
const date = new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "long", year: "numeric", timeZone: "America/Argentina/Buenos_Aires" });

const funnelLabels = {
  sessions: "Sesiones",
  product: "Vieron producto",
  cart: "Agregaron al carrito",
  checkout: "Iniciaron checkout",
  delivery: "Eligieron entrega",
  payment: "Llegaron al pago",
  paid: "Compraron",
} as const;

function percent(value: string | null) {
  return value === null ? "Sin datos" : `${percentage.format(Number(value))} %`;
}

export function WebAnalyticsDashboard({
  report,
  filters,
}: {
  report: WebAnalyticsReport;
  filters: FilterValues;
}) {
  const began = report.data_since ? date.format(new Date(report.data_since)) : null;
  const noActivity = report.kpis.sessions === 0;
  const productRows = report.tables.products.map((row) => ({ ...row, id: row.product_id }));
  const channelRows = report.tables.channels.map((row, index) => ({ ...row, id: index }));
  const deviceRows = report.tables.devices.map((row, index) => ({ ...row, id: index }));
  return (
    <div className="management-page analytics-page">
      <header className="management-page-header">
        <div>
          <h1>Métricas de la tienda</h1>
          <p>Entendé cómo llegan, avanzan y compran las personas sin enviar datos a terceros.</p>
          {began ? <p className="analytics-data-since">La medición comenzó el {began}.</p> : <p className="analytics-data-since">La medición comenzará con la primera visita registrada.</p>}
        </div>
      </header>
      <AnalyticsFilters filters={filters} />
      {noActivity ? <p className="analytics-empty">Sin datos en este período.</p> : null}
      <KpiGrid items={[
        { label: "Sesiones", value: report.kpis.sessions },
        { label: "Visitantes", value: report.kpis.visitors },
        { label: "Conversión", value: report.kpis.conversion_rate, kind: "percentage", hasDenominator: report.kpis.sessions > 0 },
        { label: "Facturación atribuida", value: report.kpis.attributed_revenue, kind: "money" },
        { label: "Ticket atribuido", value: report.kpis.average_ticket, kind: "money", hasDenominator: report.kpis.average_ticket !== null },
        { label: "Abandono de checkout", value: report.kpis.checkout_abandonment, kind: "percentage", hasDenominator: report.kpis.checkout_abandonment !== null },
      ]} />
      <p className="analytics-coverage-note">
        <span>Cobertura de atribución {percent(report.coverage.attribution_percentage)}</span>
        <small>La facturación no cubierta no se extrapola.</small>
      </p>
      <Funnel
        title="Embudo de compra"
        steps={(Object.keys(funnelLabels) as Array<keyof typeof funnelLabels>).map((key) => ({
          label: funnelLabels[key],
          count: report.funnel[key].count,
          rate: report.funnel[key].rate,
          hasDenominator: report.funnel[key].has_denominator,
        }))}
      />
      <MetricChart
        title="Actividad diaria"
        points={report.series}
        series={[
          { key: "sessions", label: "Sesiones" },
          { key: "carts", label: "Carritos" },
          { key: "orders", label: "Compras" },
        ]}
      />
      <div className="analytics-two-column">
        <section className="analytics-section">
          <div className="analytics-section-heading"><h2>Rendimiento de producto</h2><p>Interés y avance al carrito.</p></div>
          <AnalyticsDataTable
            caption="Rendimiento de productos"
            empty="No hubo vistas de producto en este período."
            rows={productRows}
            columns={[
              { key: "name", label: "Producto", render: (row) => <Link href={`/gestion/catalogo/${row.product_id}`}>{row.name}</Link> },
              { key: "views", label: "Vistas", align: "numeric" },
              { key: "cart_additions", label: "Al carrito", align: "numeric" },
              { key: "cart_rate", label: "Tasa", align: "numeric", render: (row) => percent(row.cart_rate) },
            ]}
          />
        </section>
        <section className="analytics-section">
          <div className="analytics-section-heading"><h2>Dispositivos</h2><p>Uso y conversión por formato.</p></div>
          <AnalyticsDataTable
            caption="Dispositivos"
            empty="No hubo dispositivos medidos en este período."
            rows={deviceRows}
            columns={[
              { key: "device", label: "Dispositivo" },
              { key: "sessions", label: "Sesiones", align: "numeric" },
              { key: "conversion_rate", label: "Conversión", align: "numeric", render: (row) => percent(row.conversion_rate) },
              { key: "revenue", label: "Facturación", align: "numeric", render: (row) => money.format(Number(row.revenue)) },
            ]}
          />
        </section>
      </div>
      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Canales</h2><p>Primera interacción de cada sesión.</p></div>
        <AnalyticsDataTable
          caption="Canales"
          empty="No hubo canales medidos en este período."
          rows={channelRows}
          columns={[
            { key: "source", label: "Fuente" },
            { key: "medium", label: "Medio" },
            { key: "campaign", label: "Campaña" },
            { key: "sessions", label: "Sesiones", align: "numeric" },
            { key: "conversion_rate", label: "Conversión", align: "numeric", render: (row) => percent(row.conversion_rate) },
            { key: "revenue", label: "Facturación", align: "numeric", render: (row) => money.format(Number(row.revenue)) },
          ]}
        />
      </section>
    </div>
  );
}
