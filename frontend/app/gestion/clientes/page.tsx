import { ManagementCustomerTable } from "@/components/management/customer-table";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementCustomer } from "@/lib/management/operations-types";


export default async function ManagementCustomersPage({ searchParams }: { searchParams: Promise<{ search?: string }> }) {
  const { search = "" } = await searchParams;
  const data = await managementServerGet<{ count: number; results: ManagementCustomer[] }>(`/customers/${search ? `?search=${encodeURIComponent(search)}` : ""}`);
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Clientes</p><h1>Personas y empresas</h1><p>Consultá contacto, identidad enmascarada, domicilios, datos fiscales y compras.</p></div></header><form className="management-search"><label><span className="sr-only">Buscar cliente</span><input defaultValue={search} name="search" placeholder="Buscar por nombre, email o teléfono" type="search" /></label><button className="button secondary" type="submit">Buscar</button></form><ManagementCustomerTable customers={data.results} /></div>;
}
