"use client";

import { useRouter } from "next/navigation";

import { formatMoney } from "@/lib/format";
import { managementRequest } from "@/lib/management/api";
import type { ManagementOrderDetail } from "@/lib/management/operations-types";
import { ManagementOrderActions } from "@/components/management/order-actions";
import { managementStatusLabel } from "@/components/management/order-table";


export function ManagementOrderDetailPanel({ order }: { order: ManagementOrderDetail }) {
  const router = useRouter();
  const act = async (action: string, reason: string) => {
    await managementRequest(`/orders/${order.public_id}/actions/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, reason }),
    });
    router.refresh();
  };
  return (
    <div className="management-detail-grid">
      <section className="management-form-section management-order-overview">
        <div className="management-status-row">
          <span className={`management-pill status-${order.payment_status}`}>{managementStatusLabel(order.payment_status)}</span>
          <span className="management-pill is-draft">{managementStatusLabel(order.fulfillment_status)}</span>
        </div>
        <h2>{order.customer.name}</h2>
        <p>{order.customer.email} · {order.customer.phone || "Sin teléfono"}</p>
        <dl className="management-facts">
          <div><dt>Subtotal</dt><dd>{formatMoney(order.subtotal)}</dd></div>
          <div><dt>Descuento</dt><dd>{formatMoney(order.discount)}</dd></div>
          <div><dt>Envío</dt><dd>{formatMoney(order.shipping_amount)}</dd></div>
          <div><dt>Total</dt><dd>{formatMoney(order.total)}</dd></div>
        </dl>
      </section>
      <ManagementOrderActions onAction={act} order={order} />
      <section className="management-form-section management-detail-wide">
        <h2>Productos</h2>
        {order.items.length ? <ul className="management-line-list">{order.items.map((item) => <li key={`${item.sku}-${item.quantity}`}><span><strong>{item.product_name}</strong><small>{item.sku} · {item.quantity} unidades</small></span><strong>{formatMoney(item.total)}</strong></li>)}</ul> : <p>El pedido no tiene líneas registradas.</p>}
      </section>
      <section className="management-form-section">
        <h2>Entrega</h2>
        <p>{String(order.address_snapshot.street ?? "Retiro en tienda")} {String(order.address_snapshot.number ?? "")}</p>
        <p>{String(order.address_snapshot.locality ?? "")} {String(order.address_snapshot.province ?? "")}</p>
        {order.shipment && <div className="management-notice"><strong>Seguimiento: {order.shipment.tracking_number || "Pendiente"}</strong><br />Estado: {order.shipment.status}</div>}
      </section>
      <section className="management-form-section">
        <h2>Historial</h2>
        <ol className="management-audit-list">{order.audit_events.map((event, index) => <li key={`${event.created_at}-${index}`}><strong>{managementStatusLabel(event.kind)}</strong><span>{event.actor} · {new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(new Date(event.created_at))}</span></li>)}</ol>
      </section>
    </div>
  );
}
