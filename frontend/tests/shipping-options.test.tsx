import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ManagementOrderActions } from "@/components/management/order-actions";
import { ShippingOptionSelector } from "@/components/checkout/shipping-option-selector";
import { integrationFields } from "@/lib/management/integration-fields";
import type { ManagementOrder } from "@/lib/management/operations-types";


describe("transportistas y envío a acordar", () => {
  test("Administración ofrece API MiCorreo y Andreani con credenciales de negocio", () => {
    expect(integrationFields.correo_argentino.description).toMatch(/API MiCorreo/i);
    expect(integrationFields.andreani.description).toMatch(/Andreani/i);
    expect(integrationFields.andreani.public.map((field) => field.key)).toEqual(
      expect.arrayContaining(["customer_id", "contract", "origin_postal_code"]),
    );
    expect(integrationFields.andreani.secrets.map((field) => field.key)).toEqual([
      "username",
      "password",
    ]);
  });

  test("checkout compara transportista, precio y servicio sin confundirlos", () => {
    const onSelect = vi.fn();
    render(
      <ShippingOptionSelector
        onSelect={onSelect}
        options={[
          {
            public_id: "quote-micorreo",
            provider: "correo_argentino",
            provider_label: "API MiCorreo",
            service: "CP",
            parcels: [],
            base_amount: "4500.00",
            surcharge_amount: "0.00",
            total_amount: "4500.00",
            amount_pending: false,
            currency: "ARS",
            expires_at: "2026-08-21T23:00:00-03:00",
          },
          {
            public_id: "quote-andreani",
            provider: "andreani",
            provider_label: "Andreani",
            service: "andreani_domicilio",
            parcels: [],
            base_amount: "3900.00",
            surcharge_amount: "0.00",
            total_amount: "3900.00",
            amount_pending: false,
            currency: "ARS",
            expires_at: "2026-08-21T23:00:00-03:00",
          },
        ]}
        selectedId="quote-micorreo"
      />,
    );

    expect(screen.getByText("API MiCorreo")).toBeVisible();
    expect(screen.getByText("Andreani")).toBeVisible();
    expect(screen.getByText("$ 3.900,00")).toBeVisible();
    fireEvent.click(screen.getByLabelText(/Andreani/i));
    expect(onSelect).toHaveBeenCalledWith("quote-andreani");
  });

  test("envío a acordar explica que no se cobra hasta confirmar el costo", () => {
    render(
      <ShippingOptionSelector
        onSelect={vi.fn()}
        options={[
          {
            public_id: "quote-manual",
            provider: "manual",
            provider_label: "Envío a acordar",
            service: "a_convenir",
            parcels: [],
            base_amount: "0.00",
            surcharge_amount: "0.00",
            total_amount: "0.00",
            amount_pending: true,
            currency: "ARS",
            expires_at: "2026-08-28T23:00:00-03:00",
          },
        ]}
        selectedId="quote-manual"
      />,
    );

    expect(screen.getByText("Envío a acordar")).toBeVisible();
    expect(screen.getByText(/te avisaremos el costo antes de pagar/i)).toBeVisible();
    expect(screen.queryByText("Gratis")).not.toBeInTheDocument();
  });

  test("pedido pendiente permite que el operador cargue el costo acordado", () => {
    const order: ManagementOrder = {
      public_id: "33333333-3333-4333-8333-333333333333",
      customer: { id: 5, name: "Ada", email: "ada@example.test", phone: "" },
      identity_status: "verified",
      payment_status: "not_started",
      fulfillment_status: "unfulfilled",
      fulfillment_method: "shipping",
      shipping_cost_status: "pending_agreement",
      total: "10000.00",
      created_at: "2026-08-21T10:00:00Z",
    };
    render(<ManagementOrderActions onAction={vi.fn()} order={order} />);

    fireEvent.click(screen.getByRole("button", { name: "Definir costo de envío" }));
    expect(screen.getByLabelText("Costo de envío")).toBeVisible();
    expect(screen.getByLabelText("Motivo de la acción")).toBeVisible();
  });
});
