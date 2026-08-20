import { ManagementOrderTable } from "@/components/management/order-table";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementOrder } from "@/lib/management/operations-types";


export default async function ManagementOrdersPage({ searchParams }: { searchParams: Promise<{ search?: string; attention?: string }> }) {
  const { search = "", attention = "" } = await searchParams;
  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (attention) query.set("attention", attention);
  const suffix = query.size ? `?${query}` : "";
  const data = await managementServerGet<{ count: number; results: ManagementOrder[] }>(`/orders/${suffix}`);
  return <div className="management-page">
    <header className="management-page-header"><div><p className="management-kicker">Operación</p><h1>Pedidos</h1><p>Revisá pagos, identidad, preparación, despachos y reintegros desde un solo lugar.</p></div></header>
    <form className="management-search"><label><span className="sr-only">Buscar pedido o cliente</span><input defaultValue={search} name="search" placeholder="Buscar por cliente, email o pedido" type="search" /></label><button className="button secondary" type="submit">Buscar</button><a className="button secondary" href="?attention=true">Requieren atención</a></form>
    <ManagementOrderTable orders={data.results} />
  </div>;
}
