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
        onSave={vi.fn()}
        onTest={vi.fn()}
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
        onSave={vi.fn()}
        onTest={vi.fn()}
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
        onSave={vi.fn()}
        onTest={vi.fn()}
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
        onSave={vi.fn()}
        onTest={vi.fn()}
        result="connected"
      />,
    );

    expect(screen.getByText("Mercado Pago quedó conectado.")).toBeVisible();
  });

  test("guarda la aplicación en Administración y habilita OAuth sin webhook", async () => {
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
        navigate={vi.fn()}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={onSave}
        onTest={vi.fn()}
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

  test("muestra el callback de OAuth con una acción para copiarlo", () => {
    render(
      <MercadoPagoConnectPanel
        integration={disconnected}
        navigate={vi.fn()}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        onSave={vi.fn()}
        onTest={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("URL de retorno de OAuth")).toHaveValue(
      "https://shop.example.test/api/v1/payments/mercadopago/oauth/callback/",
    );
    expect(screen.getByRole("button", { name: "Copiar URL" })).toBeVisible();
  });
});
