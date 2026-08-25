import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CartProvider } from "@/components/cart/cart-provider";
import { CheckoutFlow } from "@/components/checkout/checkout-flow";
import { clearCsrfToken } from "@/lib/api";

const accountResponses: Record<string, unknown> = {
  "/api/v1/customers/me/": {
    id: 1,
    email: "cliente@example.com",
    email_verified_at: "2026-08-24T10:00:00Z",
    is_staff: false,
    profile: { first_name: "Ada", last_name: "Compradora", phone: "1155551234" },
    masked_dni: "••••3217",
    masked_cuit: "",
  },
  "/api/v1/identity/status/": { status: "not_required", required: false },
  "/api/v1/addresses/": [
    { id: 7, label: "Casa", raw_address: "Av. de Mayo 1370", needs_review: false },
  ],
  "/api/v1/billing-profiles/": [
    { id: 9, label: "Consumidor final", legal_name: "Ada Compradora", masked_cuit: "••••5678", is_default: true },
  ],
  "/api/v1/storefront/home/": {
    settings: {
      pickup_enabled: true,
      pickup_label: "Retiro en tienda",
      pickup_address: "",
      pickup_hours: "",
    },
  },
};

const cart = {
  cart_token: "cart-token",
  subtotal: "12000.00",
  discount: "0.00",
  total: "12000.00",
  coupon: null,
  lines: [
    {
      id: 3,
      variant_id: 4,
      product_name: "Cuaderno rayado",
      variant_name: "Azul",
      quantity: 1,
      unit_price: "12000.00",
      line_total: "12000.00",
      available_stock: 5,
    },
  ],
};

afterEach(() => {
  clearCsrfToken();
  vi.unstubAllGlobals();
});

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("opciones de entrega del checkout", () => {
  test("muestra retiro cuando está habilitado aunque el punto todavía se coordine", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      return response(accountResponses[path] ?? {}, accountResponses[path] ? 200 : 404);
    }));

    render(<CheckoutFlow />);
    fireEvent.click(screen.getByRole("button", { name: "Revisar mis datos" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Elegí cómo recibir" })).toBeInTheDocument());
    expect(screen.getByRole("radio", { name: "Retiro en tienda" })).toBeVisible();
  });

  test("crea el pedido manual y deja un acceso para retomarlo después", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      if (path === "/api/v1/auth/csrf/") return response({ csrf_token: "csrf-test" });
      if (path === "/api/v1/cart/") return response(cart);
      if (accountResponses[path]) return response(accountResponses[path]);
      if (path === "/api/v1/shipping/quotes/" && method === "POST") {
        return response({
          results: [{
            public_id: "22222222-2222-4222-8222-222222222222",
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
          }],
          errors: [],
          manual_fallback: true,
        });
      }
      if (path === "/api/v1/checkout/" && method === "POST") {
        return response({
          order_id: "33333333-3333-4333-8333-333333333333",
          identity_status: "verified",
          payment_status: "not_started",
          checkout_url: "",
          shipping_cost_status: "pending_agreement",
        }, 202);
      }
      return response({ detail: "not found" }, 404);
    }));

    render(<CartProvider><CheckoutFlow /></CartProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Revisar mis datos" }));
    await screen.findByRole("heading", { name: "Elegí cómo recibir" });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cotizar envío" }));
    await screen.findByText("Envío a acordar");
    fireEvent.click(screen.getByRole("button", { name: "Solicitar coordinación" }));

    expect(await screen.findByRole("heading", { name: "Estamos coordinando el envío" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Ver pedido y seguir el estado" })).toHaveAttribute(
      "href",
      "/pedidos/33333333-3333-4333-8333-333333333333",
    );
  });
});
