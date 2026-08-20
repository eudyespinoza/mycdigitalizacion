import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { GeneralSettingsForm } from "@/components/management/general-settings-form";
import { IntegrationEditor } from "@/components/management/integration-editor";
import { IntegrationOverview } from "@/components/management/integration-overview";
import type { IntegrationConfiguration } from "@/lib/management/types";


const mercadoPago: IntegrationConfiguration = {
  provider: "mercadopago",
  label: "Mercado Pago",
  enabled: true,
  environment: "sandbox",
  status: "configured",
  public_config: { collector_id: "123456", live_mode: false },
  secret_fields: { access_token: true, webhook_secret: true },
  version: 2,
  updated_at: "2026-08-20T12:00:00Z",
  updated_by: "owner@example.test",
  last_test_status: "success",
  last_tested_at: "2026-08-20T12:01:00Z",
  last_test_message: "Conexión verificada.",
};


describe("configuración e integraciones", () => {
  test("muestra todas las integraciones con estados claros", () => {
    render(
      <IntegrationOverview
        integrations={[
          mercadoPago,
          { ...mercadoPago, provider: "correo_argentino", label: "Correo Argentino", status: "incomplete" },
          { ...mercadoPago, provider: "sid_renaper", label: "SID RENAPER", status: "disabled" },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /mercado pago/i })).toBeVisible();
    expect(screen.getByText("Configurada")).toBeVisible();
    expect(screen.getByText("Incompleta")).toBeVisible();
    expect(screen.getByText("Deshabilitada")).toBeVisible();
  });

  test("nunca rellena el secreto existente y permite reemplazarlo", async () => {
    const onSave = vi.fn().mockResolvedValue(mercadoPago);
    render(<IntegrationEditor integration={mercadoPago} onSave={onSave} />);

    const token = screen.getByLabelText("Access token");
    expect(token).toHaveValue("");
    expect(screen.getAllByText("Configurada").length).toBeGreaterThan(0);
    fireEvent.change(token, { target: { value: "nuevo-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ secrets: expect.objectContaining({ access_token: "nuevo-token" }) }),
    ));
  });

  test("edita los datos generales con etiquetas de negocio", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <GeneralSettingsForm
        initial={{
          public_name: "mycdigitalizacion",
          announcement: "",
          contact_email: "",
          pickup_enabled: true,
          pickup_label: "Retiro en tienda",
          pickup_address: "",
          pickup_hours: "",
        }}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText("Email de contacto"), {
      target: { value: "ventas@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ contact_email: "ventas@example.test" }),
    ));
  });
});
