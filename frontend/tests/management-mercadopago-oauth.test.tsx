import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { MercadoPagoConnectPanel } from "@/components/management/mercadopago-connect-panel";
import type { IntegrationConfiguration } from "@/lib/management/types";


const disconnected: IntegrationConfiguration = {
  provider: "mercadopago",
  label: "Mercado Pago",
  enabled: false,
  environment: "sandbox",
  status: "incomplete",
  public_config: {},
  secret_fields: { access_token: false, refresh_token: false, webhook_secret: false },
  version: 0,
  updated_at: null,
  updated_by: "",
  last_test_status: "",
  last_tested_at: null,
  last_test_message: "",
  oauth_ready: true,
  oauth_status: "disconnected",
  oauth_callback_url: "https://shop.example.test/api/v1/payments/mercadopago/oauth/callback/",
  connected_account_id: "",
  oauth_connected_at: null,
};


describe("conexión simple con Mercado Pago", () => {
  test("conecta con un botón sin mostrar campos de tokens", async () => {
    const onConnect = vi.fn().mockResolvedValue({
      authorization_url: "https://auth.mercadopago.com/authorization?state=safe",
      callback_url: disconnected.oauth_callback_url,
    });
    const navigate = vi.fn();

    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        navigate={navigate}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText(/access token/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/collector id/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Conectar Mercado Pago" }));

    await waitFor(() => expect(onConnect).toHaveBeenCalledTimes(1));
    expect(navigate).toHaveBeenCalledWith(
      "https://auth.mercadopago.com/authorization?state=safe",
    );
  });

  test("muestra la cuenta conectada y permite desconectarla", async () => {
    const onDisconnect = vi.fn().mockResolvedValue({ ...disconnected });
    render(
      <MercadoPagoConnectPanel
        integration={{
          ...disconnected,
          enabled: true,
          status: "configured",
          oauth_status: "connected",
          connected_account_id: "99887766",
          oauth_connected_at: "2026-08-21T12:00:00Z",
        }}
        navigate={vi.fn()}
        onConnect={vi.fn()}
        onDisconnect={onDisconnect}
      />,
    );

    expect(screen.getByText("Cuenta conectada")).toBeVisible();
    expect(screen.getByText(/99887766/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Desconectar" }));
    await waitFor(() => expect(onDisconnect).toHaveBeenCalledTimes(1));
  });

  test("explica de forma breve cuando falta preparar la aplicación", () => {
    render(
      <MercadoPagoConnectPanel
        integration={{ ...disconnected, oauth_ready: false, oauth_status: "not_ready" }}
        navigate={vi.fn()}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Conectar Mercado Pago" })).toBeDisabled();
    expect(screen.getByText(/falta habilitar la conexión segura/i)).toBeVisible();
  });

  test("confirma el regreso exitoso desde Mercado Pago", () => {
    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        navigate={vi.fn()}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        result="connected"
      />,
    );

    expect(screen.getByText("Mercado Pago quedó conectado.")).toBeVisible();
  });
});
