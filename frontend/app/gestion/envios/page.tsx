import Link from "next/link";

import { ManagementShippingPanel } from "@/components/management/shipping-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ShippingBox } from "@/lib/management/operations-types";


export default async function ManagementShippingPage() {
  const data = await managementServerGet<{ results: ShippingBox[] }>("/shipping/boxes/");
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Logística</p><h1>Envíos y embalajes</h1><p>Definí las cajas que usa el cálculo automático y accedé a la configuración del transportista.</p></div><Link className="button secondary" href="/gestion/integraciones/correo_argentino">Configurar Correo Argentino</Link></header><div className="management-content-gap"><ManagementShippingPanel boxes={data.results} /></div></div>;
}
