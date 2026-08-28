"use client";

import { WarningCircle } from "@phosphor-icons/react";
import { FormEvent, useState } from "react";

import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { formatMoney } from "@/lib/format";
import type { ManagementOrder } from "@/lib/management/operations-types";


export type ManagementOrderActionOptions = {
  confirmRefund?: boolean;
  shippingAmount?: string;
};


export function ManagementOrderActions({
  order,
  onAction,
}: {
  order: ManagementOrder;
  onAction: (
    action: string,
    reason: string,
    options?: ManagementOrderActionOptions,
  ) => Promise<void>;
}) {
  const [action, setAction] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const paidCancellation = action === "cancel" && order.payment_status === "paid";
  const approvedMercadoPagoPayment = order.payments?.find(
    (payment) => payment.provider === "mercadopago" && payment.status === "approved",
  );
  const refundAmount = approvedMercadoPagoPayment?.amount ?? order.total;
  const refundAmountLabel = formatMoney(refundAmount);
  const canCancel = !["cancelled", "shipped", "fulfilled"].includes(
    order.fulfillment_status,
  ) && !["pending", "needs_attention"].includes(order.payment_status);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!action) return;
    const form = new FormData(event.currentTarget);
    const reason = String(form.get("reason") ?? "");
    const shippingAmount = String(form.get("shipping_amount") ?? "");
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (action === "set_shipping_cost") {
        await onAction(action, reason, { shippingAmount });
      } else if (paidCancellation) {
        await onAction(action, reason, { confirmRefund: true });
      } else {
        await onAction(action, reason);
      }
      setAction(null);
      setNotice(
        paidCancellation
          ? "Pedido cancelado y reintegro registrado correctamente."
          : "Acción registrada correctamente.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  };
  const available: Array<[string, string]> = [];
  if (order.identity_status === "manual_review") {
    available.push(["approve_identity", "Aprobar identidad"]);
  }
  if (order.payment_status === "paid") {
    available.push(["refund", "Reintegrar pago"]);
  }
  if (canCancel) {
    available.push(["cancel", "Cancelar pedido"]);
  }
  if (order.shipping_cost_status === "pending_agreement") {
    available.push(["set_shipping_cost", "Definir costo de envío"]);
  }
  if (
    order.payment_status === "paid"
    && order.fulfillment_method === "shipping"
    && order.shipping_provider !== "manual"
    && order.fulfillment_status === "unfulfilled"
  ) {
    available.push(["create_shipment", "Crear envío"]);
  }
  if (order.payment_status === "paid" && order.fulfillment_status === "unfulfilled") {
    available.push(["mark_preparing", "Marcar en preparación"]);
  }
  if (order.fulfillment_method === "pickup" && order.fulfillment_status === "preparing") {
    available.push(["mark_ready_for_pickup", "Listo para retirar"]);
  }
  if (["shipped", "ready_for_pickup"].includes(order.fulfillment_status)) {
    available.push(["mark_fulfilled", "Marcar entregado"]);
  }

  const dialogTitle = paidCancellation
    ? "Cancelar pedido y devolver el pago"
    : action === "cancel"
      ? "Cancelar pedido"
      : action === "refund"
        ? "Reintegrar pago"
        : action === "set_shipping_cost"
          ? "Definir costo de envío"
          : "Confirmar acción";
  const dialogDescription = paidCancellation
    ? "Esta operación cancela el pedido después de que Mercado Pago acepte el reintegro total."
    : action === "refund"
      ? "El importe se devolverá por el mismo medio de pago y quedará registrado en el historial."
      : action === "cancel"
        ? "El pedido quedará cancelado y se liberarán las reservas asociadas."
        : "Indicá el motivo para dejar la operación registrada en el historial.";
  const confirmLabel = paidCancellation
    ? `Cancelar y devolver ${refundAmountLabel}`
    : action === "cancel"
      ? "Confirmar cancelación"
      : action === "refund"
        ? `Reintegrar ${refundAmountLabel}`
        : "Confirmar";

  return (
    <section className="management-form-section management-order-actions">
      <p className="management-kicker">Acciones</p>
      <h2>Gestionar pedido</h2>
      <div className="management-action-list">
        {available.map(([value, label]) => (
          <button
            className={value === "refund" || value === "cancel" ? "button danger" : "button secondary"}
            key={value}
            onClick={() => {
              setError("");
              setAction(value);
            }}
            type="button"
          >
            {label}
          </button>
        ))}
        {!available.length && <p>No hay acciones manuales disponibles para este estado.</p>}
      </div>
      {notice && <p className="management-notice" role="status">{notice}</p>}
      <ManagementFormDialog
        description={dialogDescription}
        onClose={() => {
          if (!busy) setAction(null);
        }}
        open={Boolean(action)}
        title={dialogTitle}
      >
        <form
          aria-busy={busy}
          className="management-form management-action-dialog-form"
          onSubmit={(event) => void submit(event)}
        >
          {(paidCancellation || action === "refund") && (
            <div className="management-refund-warning">
              <span aria-hidden="true" className="management-refund-warning-icon">
                <WarningCircle size={24} weight="bold" />
              </span>
              <div>
                <strong>Reintegro total por Mercado Pago</strong>
                <p>
                  Mercado Pago devolverá {refundAmountLabel} al medio de pago utilizado.
                  {approvedMercadoPagoPayment?.payment_id
                    ? ` Pago ${approvedMercadoPagoPayment.payment_id}.`
                    : " El sistema verificará el pago asociado antes de continuar."}
                </p>
              </div>
            </div>
          )}
          {action === "set_shipping_cost" && (
            <label>
              <span>Costo de envío</span>
              <input min="0" name="shipping_amount" required step="0.01" type="number" />
            </label>
          )}
          <label>
            <span>{action === "cancel" ? "Motivo de la cancelación" : "Motivo de la acción"}</span>
            <textarea maxLength={500} name="reason" required rows={4} />
          </label>
          {error && <p className="inline-error" role="alert">{error}</p>}
          <div className="management-form-actions">
            <button
              className={action === "cancel" || action === "refund" ? "button destructive" : "button primary"}
              disabled={busy}
              type="submit"
            >
              {busy ? "Procesando…" : confirmLabel}
            </button>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setAction(null)}
              type="button"
            >
              Volver
            </button>
          </div>
        </form>
      </ManagementFormDialog>
    </section>
  );
}
