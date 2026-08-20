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
    fireEvent.change(screen.getByLabelText("Motivo de la acción"), {
      target: { value: "Solicitud del cliente" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith("cancel", "Solicitud del cliente"));
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
    expect(screen.getByText("••••3456")).toBeVisible();
    expect(screen.queryByText("30123456")).not.toBeInTheDocument();
  });

  test("carga embalajes con todas sus medidas", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<ShippingBoxPanel boxes={[]} onCreate={onCreate} />);
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
