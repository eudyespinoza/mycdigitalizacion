import Link from "next/link";

import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementDashboard } from "@/lib/management/types";


const metricCopy = {
  active_products: ["Productos activos", "/gestion/catalogo"],
  low_stock_variants: ["Stock bajo", "/gestion/inventario"],
  orders_requiring_attention: ["Pedidos para revisar", "/gestion/pedidos?attention=1"],
  integration_incidents: ["Alertas de integraciones", "/gestion/integraciones"],
} as const;


export default async function ManagementDashboardPage() {
  const dashboard = await managementServerGet<ManagementDashboard>("/dashboard/");
  return (
    <div className="management-page">
      <header className="management-page-header">
        <div>
          <p className="management-kicker">Resumen operativo</p>
          <h1>Todo lo importante, en un solo lugar</h1>
          <p>Revisá el estado de la tienda y entrá directo a lo que necesita atención.</p>
        </div>
        <Link className="button primary" href="/gestion/catalogo/nuevo">Cargar producto</Link>
      </header>
      <section className="management-metrics" aria-label="Indicadores de la tienda">
        {Object.entries(dashboard.metrics).map(([key, value]) => {
          const [label, href] = metricCopy[key as keyof typeof metricCopy];
          return (
            <Link href={href} key={key}>
              <span>{label}</span>
              <strong>{value}</strong>
              <small>Ver detalle</small>
            </Link>
          );
        })}
      </section>
      <section className="management-welcome">
        <div>
          <p className="management-kicker">Configuración</p>
          <h2>Prepará la tienda para vender</h2>
          <p>Completá pagos, envíos, identidad, correos y datos generales desde pantallas propias.</p>
        </div>
        <Link className="button secondary" href="/gestion/integraciones">Configurar integraciones</Link>
      </section>
    </div>
  );
}
