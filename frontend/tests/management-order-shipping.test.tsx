import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ManagementOrderDetailPanel } from "@/components/management/order-detail-panel";
import type { ManagementOrderDetail } from "@/lib/management/operations-types";


vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));


const order: ManagementOrderDetail = {
  public_id: "2fc81ca1-9b37-4f90-85d9-2b6852a52c99",
  customer: { id: 7, name: "Ana Pérez", email: "cliente@example.test", phone: "1122334455" },
  identity_status: "verified",
  payment_status: "paid",
  fulfillment_status: "unfulfilled",
  fulfillment_method: "shipping",
  shipping_cost_status: "ready",
  shipping_provider: "andreani",
  total: "12500.00",
  created_at: "2026-08-20T12:00:00Z",
  customer_snapshot: {},
  address_snapshot: { street: "Av. de Mayo", number: "1370", locality: "CABA" },
  fiscal_snapshot: {},
  subtotal: "10000.00",
  discount: "0.00",
  shipping_amount: "2500.00",
  items: [],
  audit_events: [],
  payments: [],
  shipment: null,
};


describe("despacho Andreani en gestión de pedidos", () => {
  test("ofrece crear el envío sólo con pago e identidad aprobados", () => {
    const { rerender } = render(<ManagementOrderDetailPanel order={order} />);

    expect(screen.getByRole("button", { name: "Crear envío" })).toBeVisible();

    rerender(<ManagementOrderDetailPanel order={{ ...order, identity_status: "manual_review" }} />);

    expect(screen.queryByRole("button", { name: "Crear envío" })).not.toBeInTheDocument();
  });

  test("muestra el procesamiento sin habilitar una etiqueta prematura", () => {
    render(<ManagementOrderDetailPanel order={{
      ...order,
      shipment: {
        provider: "andreani",
        tracking_number: "360000036137650",
        status: "importing",
        label_url: "",
        updated_at: "2026-08-20T12:05:00Z",
      },
    }} />);

    expect(screen.getByText("Procesando en Andreani")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Crear envío" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Descargar etiqueta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Imprimir etiqueta" })).not.toBeInTheDocument();
  });

  test("habilita descarga e impresión sólo cuando el PDF interno está listo", () => {
    const labelUrl = `/api/v1/orders/${order.public_id}/label/`;
    render(<ManagementOrderDetailPanel order={{
      ...order,
      shipment: {
        provider: "andreani",
        tracking_number: "360000036137650",
        status: "imported",
        label_url: labelUrl,
        updated_at: "2026-08-20T12:05:00Z",
      },
    }} />);

    expect(screen.getByRole("link", { name: "Descargar etiqueta" })).toHaveAttribute(
      "href",
      labelUrl,
    );
    expect(screen.getByRole("link", { name: "Imprimir etiqueta" })).toHaveAttribute(
      "href",
      `${labelUrl}?preview=1`,
    );
  });
});
