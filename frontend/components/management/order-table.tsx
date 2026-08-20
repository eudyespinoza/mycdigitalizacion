import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { ManagementOrder } from "@/lib/management/operations-types";


const statusLabels: Record<string, string> = {
  pending_identity: "Identidad pendiente",
  manual_review: "Revisión de identidad",
  verified: "Identidad validada",
  not_started: "Pago no iniciado",
  pending: "Pago pendiente",
  paid: "Pago acreditado",
  failed: "Pago rechazado",
  refunded: "Pago reintegrado",
  needs_attention: "Requiere atención",
  unfulfilled: "Pendiente de preparación",
  preparing: "En preparación",
  shipped: "Despachado",
  ready_for_pickup: "Listo para retirar",
  fulfilled: "Entregado",
  cancelled: "Cancelado",
};


export function managementStatusLabel(value: string) {
  return statusLabels[value] ?? value.replaceAll("_", " ");
}


export function ManagementOrderTable({ orders }: { orders: ManagementOrder[] }) {
  if (!orders.length) {
    return <div className="management-empty"><h2>No hay pedidos</h2><p>Los pedidos nuevos aparecerán acá.</p></div>;
  }
  return (
    <div className="management-table-wrap">
      <table className="management-table">
        <thead><tr><th>Pedido</th><th>Cliente</th><th>Pago</th><th>Entrega</th><th>Total</th><th>Fecha</th></tr></thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.public_id}>
              <td><Link href={`/gestion/pedidos/${order.public_id}`}>#{order.public_id.slice(0, 8)}</Link><small>{order.fulfillment_method === "pickup" ? "Retiro" : "Envío"}</small></td>
              <td><Link href={`/gestion/pedidos/${order.public_id}`}>{order.customer.name}</Link><small>{order.customer.email}</small></td>
              <td><span className={`management-pill status-${order.payment_status}`}>{managementStatusLabel(order.payment_status)}</span></td>
              <td>{managementStatusLabel(order.fulfillment_status)}</td>
              <td><strong>{formatMoney(order.total)}</strong></td>
              <td>{new Intl.DateTimeFormat("es-AR", { dateStyle: "short" }).format(new Date(order.created_at))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
