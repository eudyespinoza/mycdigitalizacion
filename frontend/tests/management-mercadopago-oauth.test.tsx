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
  webhook_ready: false,
};


describe("conexión simple con Mercado Pago", () => {
  test("conecta con un botón sin mostrar campos de tokens", async () => {
    const onConnect = vi.fn().mockResolvedValue({
      ...disconnected,
      enabled: true,
      status: "configured",
      oauth_status: "connected",
      connected_account_id: "99887766",
    });

    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText(/access token/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/collector id/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Conectar Mercado Pago" }));

    await waitFor(() => expect(onConnect).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Cuenta conectada")).toBeVisible();
    expect(screen.getByText(/99887766/)).toBeVisible();
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
          public_config: { connected_brand_name: "La Torre" },
        }}
        onConnect={vi.fn()}
        onDisconnect={onDisconnect}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("Cuenta conectada")).toBeVisible();
    expect(screen.getByText(/99887766/)).toBeVisible();
    expect(screen.getByText(/Mercado Pago identifica esta cuenta como “La Torre”/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Desconectar" }));
    await waitFor(() => expect(onDisconnect).toHaveBeenCalledTimes(1));
  });

  test("explica de forma breve cuando falta preparar la aplicación", () => {
    render(
      <MercadoPagoConnectPanel
        integration={{ ...disconnected, oauth_ready: false, oauth_status: "not_ready" }}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Conectar Mercado Pago" })).toBeDisabled();
    expect(screen.getByText(/falta habilitar la conexión segura/i)).toBeVisible();
  });

  test("confirma el regreso exitoso desde Mercado Pago", () => {
    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={vi.fn()}
        result="connected"
      />,
    );

    expect(screen.getByText("Mercado Pago quedó conectado.")).toBeVisible();
  });

  test("guarda la aplicación en Administración y habilita la conexión sin webhook", async () => {
    const configured = {
      ...disconnected,
      environment: "production" as const,
      public_config: { oauth_client_id: "app-123456" },
      secret_fields: {
        ...disconnected.secret_fields,
        oauth_client_secret: true,
      },
      oauth_ready: true,
      webhook_ready: false,
      version: 1,
    };
    const onSave = vi.fn().mockResolvedValue(configured);

    render(
      <MercadoPagoConnectPanel
        integration={{ ...disconnected, oauth_ready: false, oauth_status: "not_ready" }}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText("ID de aplicación (Client ID)"), {
      target: { value: "app-123456" },
    });
    fireEvent.change(screen.getByLabelText("Client Secret"), {
      target: { value: "protected-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith({
      environment: "production",
      public_config: { oauth_client_id: "app-123456" },
      secrets: {
        oauth_client_secret: "protected-secret",
        webhook_secret: "",
      },
    }));
    expect(screen.getByRole("button", { name: "Conectar Mercado Pago" })).toBeEnabled();
    expect(screen.getByText(/falta configurar la firma del webhook/i)).toBeVisible();
  });

  test("no pide URL de retorno porque conecta la cuenta propia", () => {
    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText("URL de retorno de OAuth")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copiar URL" })).not.toBeInTheDocument();
    expect(screen.getByText(/cuenta propia de la tienda/i)).toBeVisible();
  });

});
