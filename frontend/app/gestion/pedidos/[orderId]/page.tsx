import Link from "next/link";

import { ManagementOrderDetailPanel } from "@/components/management/order-detail-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementOrderDetail } from "@/lib/management/operations-types";


export default async function ManagementOrderPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  const order = await managementServerGet<ManagementOrderDetail>(`/orders/${orderId}/`);
  return <div className="management-page management-editor-page"><Link className="management-back" href="/gestion/pedidos">← Volver a pedidos</Link><header className="management-page-header"><div><p className="management-kicker">Pedido</p><h1>#{order.public_id.slice(0, 8)}</h1><p>Detalle operativo, pagos, entrega y acciones auditadas.</p></div></header><ManagementOrderDetailPanel order={order} /></div>;
}
