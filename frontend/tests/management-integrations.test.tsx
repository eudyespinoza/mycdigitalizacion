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
    const smtp: IntegrationConfiguration = {
      ...mercadoPago,
      provider: "smtp",
      label: "Correo transaccional",
      public_config: {
        host: "smtp.example.test",
        port: 587,
        use_tls: true,
        from_email: "ventas@example.test",
      },
      secret_fields: { username: true, password: true },
    };
    const onSave = vi.fn().mockResolvedValue(smtp);
    render(<IntegrationEditor integration={smtp} onSave={onSave} />);

    const password = screen.getByLabelText("Contraseña");
    expect(password).toHaveValue("");
    expect(screen.getAllByText("Configurada").length).toBeGreaterThan(0);
    fireEvent.change(password, { target: { value: "nueva-clave" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ secrets: expect.objectContaining({ password: "nueva-clave" }) }),
    ));
  });

  test("carga certificados ARCA como texto o base64 sin rellenar secretos guardados", async () => {
    const arca: IntegrationConfiguration = {
      ...mercadoPago,
      provider: "arca_a13",
      label: "Identidad fiscal ARCA · Padrón A13",
      environment: "production",
      public_config: { represented_cuit: "20123456786" },
      secret_fields: {
        certificate_pem: false,
        private_key_pem: false,
        private_key_passphrase: false,
        pfx_base64: false,
        pfx_password: false,
      },
    };
    const onSave = vi.fn().mockResolvedValue(arca);
    render(<IntegrationEditor integration={arca} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Certificado ARCA (.crt o .pem)"), {
      target: { files: [new File(["CERTIFICATE"], "arca.crt", { type: "application/x-pem-file" })] },
    });
    fireEvent.change(screen.getByLabelText("Clave privada ARCA (.key o .pem)"), {
      target: { files: [new File(["PRIVATE KEY"], "arca.key", { type: "application/x-pem-file" })] },
    });
    fireEvent.change(screen.getByLabelText("Certificado ARCA (.pfx o .p12)"), {
      target: { files: [new File([new Uint8Array([1, 2, 3])], "arca.pfx")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      secrets: expect.objectContaining({
        certificate_pem: "CERTIFICATE",
        private_key_pem: "PRIVATE KEY",
        pfx_base64: "AQID",
      }),
    })));
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
          instagram_url: "",
          facebook_url: "",
          tiktok_url: "",
          youtube_url: "",
          linkedin_url: "",
          whatsapp_enabled: false,
          whatsapp_number: "",
          whatsapp_message: "",
          theme_palette: "pulso",
          theme_structure: "#020530",
          theme_action: "#BD1D59",
          theme_wayfinding: "#007F96",
          theme_background: "#FFFFFF",
          theme_text: "#020530",
        }}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText("Email de contacto"), {
      target: { value: "ventas@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Instagram"), {
      target: { value: "https://instagram.com/mycdigitalizacion" },
    });
    fireEvent.click(screen.getByLabelText("Mostrar botón de WhatsApp"));
    fireEvent.change(screen.getByLabelText("Número de WhatsApp"), {
      target: { value: "+54 9 11 5555-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        contact_email: "ventas@example.test",
        instagram_url: "https://instagram.com/mycdigitalizacion",
        whatsapp_enabled: true,
        whatsapp_number: "+54 9 11 5555-1234",
      }),
    ));
  });
});
