import Link from "next/link";

import { ManagementShippingPanel } from "@/components/management/shipping-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ShippingBox } from "@/lib/management/operations-types";


export default async function ManagementShippingPage() {
  const data = await managementServerGet<{ results: ShippingBox[] }>("/shipping/boxes/");
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Logística</p><h1>Envíos y embalajes</h1><p>Definí las cajas del cálculo automático y conectá uno o más transportistas.</p></div><div className="management-form-actions"><Link className="button secondary" href="/gestion/integraciones/correo_argentino">Configurar API MiCorreo</Link><Link className="button secondary" href="/gestion/integraciones/andreani">Configurar Andreani</Link></div></header><div className="management-content-gap"><ManagementShippingPanel boxes={data.results} /></div></div>;
}
