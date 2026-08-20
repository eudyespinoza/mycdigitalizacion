import { InventoryPanel } from "@/components/management/inventory-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementVariant } from "@/lib/management/catalog-types";


export default async function InventoryPage() {
  const data = await managementServerGet<{ count: number; results: ManagementVariant[] }>("/inventory/");
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Catálogo</p><h1>Inventario</h1><p>Stock físico, reservado y disponible de {data.count} variantes.</p></div></header><div className="management-content-gap"><InventoryPanel variants={data.results} /></div></div>;
}
