import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { CheckoutFlow } from "@/components/checkout/checkout-flow";

afterEach(() => vi.unstubAllGlobals());

test("checkout keeps completed data visible with a check before advancing without RENAPER", async () => {
  const responses: Record<string, unknown> = {
    "/api/v1/customers/me/": {
      id: 1,
      email: "cliente@example.com",
      email_verified_at: "2026-08-24T10:00:00Z",
      is_staff: false,
      profile: { first_name: "Ricardo", last_name: "Savio", phone: "1155551234" },
      masked_dni: "••••3217",
      masked_cuit: "",
    },
    "/api/v1/identity/status/": { status: "not_required", required: false },
    "/api/v1/addresses/": [],
    "/api/v1/billing-profiles/": [],
    "/api/v1/storefront/home/": {
      settings: { pickup_enabled: false, pickup_label: "", pickup_address: "", pickup_hours: "" },
    },
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://localhost").pathname;
    return new Response(JSON.stringify(responses[path]), {
      status: responses[path] ? 200 : 404,
      headers: { "Content-Type": "application/json" },
    });
  }));

  render(<CheckoutFlow />);
  fireEvent.click(screen.getByRole("button", { name: "Revisar mis datos" }));

  await waitFor(() => expect(screen.getByText("Datos completos")).toBeVisible());
  expect(screen.getByText("Ricardo Savio")).toBeVisible();
  expect(screen.getByText(/DNI ••••3217/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Tus datos" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Elegí cómo recibir" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Autorizo la verificación/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Verificar mis datos" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Continuar a entrega" }));

  expect(screen.getByRole("heading", { name: "Elegí cómo recibir" })).toBeVisible();
});
