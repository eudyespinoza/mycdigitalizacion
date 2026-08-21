"use client";

import { FormEvent, useState } from "react";

import type { ManagementOrder } from "@/lib/management/operations-types";


export function ManagementOrderActions({
  order,
  onAction,
}: {
  order: ManagementOrder;
  onAction: (action: string, reason: string, shippingAmount?: string) => Promise<void>;
}) {
  const [action, setAction] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!action) return;
    const form = new FormData(event.currentTarget);
    const reason = String(form.get("reason") ?? "");
    const shippingAmount = String(form.get("shipping_amount") ?? "");
    setBusy(true);
    setMessage("");
    try {
      if (action === "set_shipping_cost") {
        await onAction(action, reason, shippingAmount);
      } else {
        await onAction(action, reason);
      }
      setAction(null);
      setMessage("Acción registrada correctamente.");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  };
  const available = [
    ...(order.identity_status === "manual_review" ? [["approve_identity", "Aprobar identidad"]] : []),
    ...(order.payment_status === "paid" ? [["refund", "Reintegrar pago"]] : []),
    ...(order.payment_status === "failed" || order.payment_status === "not_started" ? [["cancel", "Cancelar pedido"]] : []),
    ...(order.shipping_cost_status === "pending_agreement" ? [["set_shipping_cost", "Definir costo de envío"]] : []),
    ...(order.payment_status === "paid" && order.fulfillment_method === "shipping" && order.shipping_provider !== "manual" && order.fulfillment_status === "unfulfilled" ? [["create_shipment", "Crear envío"]] : []),
    ...(order.payment_status === "paid" && order.fulfillment_status === "unfulfilled" ? [["mark_preparing", "Marcar en preparación"]] : []),
    ...(order.fulfillment_method === "pickup" && order.fulfillment_status === "preparing" ? [["mark_ready_for_pickup", "Listo para retirar"]] : []),
    ...(order.fulfillment_status === "shipped" || order.fulfillment_status === "ready_for_pickup" ? [["mark_fulfilled", "Marcar entregado"]] : []),
  ];
  return (
    <section className="management-form-section management-order-actions">
      <p className="management-kicker">Acciones</p>
      <h2>Gestionar pedido</h2>
      <div className="management-action-list">
        {available.map(([value, label]) => (
          <button className={value === "refund" || value === "cancel" ? "button danger" : "button secondary"} key={value} onClick={() => setAction(value)} type="button">{label}</button>
        ))}
        {!available.length && <p>No hay acciones manuales disponibles para este estado.</p>}
      </div>
      {message && <p className="management-notice" role="status">{message}</p>}
      {action && (
        <div className="management-dialog-layer" role="presentation">
          <form aria-label="Confirmar acción sobre pedido" className="management-dialog" onSubmit={(event) => void submit(event)}>
            <div><p className="management-kicker">Confirmación</p><h2>{action === "cancel" ? "Cancelar pedido" : action === "set_shipping_cost" ? "Definir costo de envío" : "Confirmar acción"}</h2></div>
            {action === "set_shipping_cost" && <label><span>Costo de envío</span><input min="0" name="shipping_amount" required step="0.01" type="number" /></label>}
            <label><span>Motivo de la acción</span><textarea maxLength={500} name="reason" required rows={4} /></label>
            <div className="management-form-actions">
              <button className="button primary" disabled={busy} type="submit">{action === "cancel" ? "Confirmar cancelación" : "Confirmar"}</button>
              <button className="button secondary" onClick={() => setAction(null)} type="button">Volver</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
