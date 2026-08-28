import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ManagementCustomerTable } from "@/components/management/customer-table";
import { ManagementOrderActions } from "@/components/management/order-actions";
import { ManagementOrderTable } from "@/components/management/order-table";
import { ShippingBoxPanel } from "@/components/management/shipping-box-panel";


const order = {
  public_id: "2fc81ca1-9b37-4f90-85d9-2b6852a52c99",
  customer: { id: 7, name: "Ana Pérez", email: "cliente@example.test", phone: "1122334455" },
  identity_status: "verified",
  payment_status: "failed",
  fulfillment_status: "unfulfilled",
  fulfillment_method: "shipping",
  total: "12500.00",
  created_at: "2026-08-20T12:00:00Z",
};


describe("gestión operativa", () => {
  test("lista pedidos con estados entendibles y acceso al detalle", () => {
    render(<ManagementOrderTable orders={[order]} />);
    expect(screen.getByRole("link", { name: /Ana Pérez/ })).toHaveAttribute(
      "href",
      `/gestion/pedidos/${order.public_id}`,
    );
    expect(screen.getByText("Pago rechazado")).toBeVisible();
    expect(screen.getByText("$ 12.500,00")).toBeVisible();
  });

  test("confirma una acción sensible con motivo", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(<ManagementOrderActions onAction={onAction} order={order} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancelar pedido" }));
    fireEvent.change(screen.getByLabelText("Motivo de la cancelación"), {
      target: { value: "Solicitud del cliente" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith("cancel", "Solicitud del cliente"));
  });

  test("permite cancelar un pedido no entregado con pago pendiente", () => {
    render(<ManagementOrderActions onAction={vi.fn()} order={{
      ...order,
      payment_status: "pending",
    }} />);

    expect(screen.getByRole("button", { name: "Cancelar pedido" })).toBeVisible();
  });

  test("mantiene protegido un pedido cuyo pago requiere revisión", () => {
    render(<ManagementOrderActions onAction={vi.fn()} order={{
      ...order,
      payment_status: "needs_attention",
    }} />);

    expect(screen.queryByRole("button", { name: "Cancelar pedido" })).not.toBeInTheDocument();
  });

  test("advierte y confirma el reintegro al cancelar un pedido pagado", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(<ManagementOrderActions onAction={onAction} order={{
      ...order,
      payment_status: "paid",
      payments: [{
        provider: "mercadopago",
        status: "approved",
        provider_status: "approved",
        payment_id: "mp-payment-12500",
        amount: "12500.00",
        currency: "ARS",
        created_at: "2026-08-20T12:05:00Z",
      }],
    }} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancelar pedido" }));

    expect(screen.getByRole("dialog", { name: "Cancelar pedido y devolver el pago" })).toBeVisible();
    expect(screen.getByText(/Mercado Pago devolverá \$ 12\.500,00/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Motivo de la cancelación"), {
      target: { value: "El cliente solicitó cancelar la compra" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Cancelar y devolver.*12\.500,00/ }));

    await waitFor(() => expect(onAction).toHaveBeenCalledWith(
      "cancel",
      "El cliente solicitó cancelar la compra",
      { confirmRefund: true },
    ));
  });

  test("mantiene abierto el diálogo si Mercado Pago no confirma la devolución", async () => {
    const onAction = vi.fn().mockRejectedValue(
      new Error("No pudimos comunicarnos con Mercado Pago. El pedido sigue activo; intentá nuevamente."),
    );
    render(<ManagementOrderActions onAction={onAction} order={{
      ...order,
      payment_status: "paid",
      payments: [{
        provider: "mercadopago",
        status: "approved",
        provider_status: "approved",
        payment_id: "mp-payment-12500",
        amount: "12500.00",
        currency: "ARS",
        created_at: "2026-08-20T12:05:00Z",
      }],
    }} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancelar pedido" }));
    fireEvent.change(screen.getByLabelText("Motivo de la cancelación"), {
      target: { value: "Solicitud del cliente" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Cancelar y devolver/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos comunicarnos con Mercado Pago. El pedido sigue activo; intentá nuevamente.",
    );
    expect(screen.getByRole("dialog", { name: "Cancelar pedido y devolver el pago" })).toBeVisible();
    expect(screen.getByLabelText("Motivo de la cancelación")).toHaveValue("Solicitud del cliente");
    expect(screen.getByRole("button", { name: /Cancelar y devolver/ })).toBeEnabled();
  });

  test("muestra clientes sin revelar el DNI completo", () => {
    render(<ManagementCustomerTable customers={[{
      id: 7,
      name: "Ana Pérez",
      email: "cliente@example.test",
      phone: "1122334455",
      masked_dni: "••••3456",
      order_count: 1,
      total_spent: "12500.00",
      email_verified: true,
    }]} />);
    expect(screen.getByRole("link", { name: "Abrir ficha completa de Ana Pérez" })).toHaveAttribute(
      "href",
      "/gestion/clientes/7",
    );
    expect(screen.getByText("••••3456")).toBeVisible();
    expect(screen.queryByText("30123456")).not.toBeInTheDocument();
  });

  test("carga embalajes con todas sus medidas", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<ShippingBoxPanel boxes={[]} onCreate={onCreate} />);
    expect(screen.queryByLabelText("Código")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Agregar embalaje" }));
    fireEvent.change(screen.getByLabelText("Código"), { target: { value: "CAJA-M" } });
    fireEvent.change(screen.getByLabelText("Largo interior (cm)"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Ancho interior (cm)"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Alto interior (cm)"), { target: { value: "15" } });
    fireEvent.change(screen.getByLabelText("Tara (g)"), { target: { value: "250" } });
    fireEvent.change(screen.getByLabelText("Peso máximo (g)"), { target: { value: "10000" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar embalaje" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      code: "CAJA-M",
      max_weight_grams: 10000,
    })));
  });
});
