import { ManagementAuditTable } from "@/components/management/audit-table";
import type { ManagementAuditEvent } from "@/lib/management/access-types";
import { managementServerGet } from "@/lib/management/server-api";


export default async function ManagementAuditPage({ searchParams }: { searchParams: Promise<{ search?: string }> }) {
  const { search = "" } = await searchParams;
  const data = await managementServerGet<{ count: number; results: ManagementAuditEvent[] }>(`/audit/${search ? `?search=${encodeURIComponent(search)}` : ""}`);
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Control</p><h1>Auditoría</h1><p>Historial inmutable de cambios sensibles realizados desde el panel.</p></div></header><form className="management-search"><label><span className="sr-only">Buscar en auditoría</span><input defaultValue={search} name="search" placeholder="Buscar acción, usuario o recurso" type="search" /></label><button className="button secondary" type="submit">Buscar</button></form><ManagementAuditTable events={data.results} /></div>;
}
