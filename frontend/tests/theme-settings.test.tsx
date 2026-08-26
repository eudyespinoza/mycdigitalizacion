import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { GeneralSettingsForm } from "@/components/management/general-settings-form";
import { ManagementShell } from "@/components/management/management-shell";
import { SiteFooter } from "@/components/layout/site-footer";
import { BrandProvider } from "@/components/layout/brand-provider";
import { ApiError } from "@/lib/api";
import { FALLBACK_BRANDING } from "@/lib/branding";
import { resolveThemeVariables } from "@/lib/theme";


const initial = {
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
  theme_palette: "pulso" as const,
  theme_structure: "#020530",
  theme_action: "#BD1D59",
  theme_wayfinding: "#007F96",
  theme_background: "#FFFFFF",
  theme_text: "#020530",
};


describe("tema global y marcas sociales", () => {
  test("convierte la paleta guardada en variables semánticas globales", () => {
    expect(resolveThemeVariables(initial)).toMatchObject({
      "--ink": "#020530",
      "--blue": "#020530",
      "--magenta-action": "#BD1D59",
      "--cyan-action": "#007F96",
      "--surface": "#FFFFFF",
    });
  });

  test("permite elegir una paleta personalizada y envía sus cinco roles", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<GeneralSettingsForm initial={initial} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Paleta"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Color de acción"), { target: { value: "#9c2f4a" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      theme_palette: "custom",
      theme_structure: "#020530",
      theme_action: "#9C2F4A",
      theme_wayfinding: "#007F96",
      theme_background: "#FFFFFF",
      theme_text: "#020530",
    })));
  });

  test("explica qué color necesita corregirse cuando falla el contraste", async () => {
    const onSave = vi.fn().mockRejectedValue(new ApiError(
      400,
      "validation_error",
      "Revisá los datos ingresados.",
      { theme_action: ["El color de acción necesita más contraste con texto blanco."] },
    ));
    render(<GeneralSettingsForm initial={initial} onSave={onSave} />);

    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El color de acción necesita más contraste con texto blanco.",
    );
  });

  test("identifica el espacio operativo como Administración", () => {
    render(
      <ManagementShell session={{ user: {
        id: 1,
        email: "owner@example.test",
        first_name: "Ada",
        last_name: "Lovelace",
        is_staff: true,
        is_superuser: true,
        permissions: [],
      } }}>
        <p>Contenido</p>
      </ManagementShell>,
    );

    const brand = screen.getByRole("link", { name: "Inicio de Administración" });
    expect(brand).toHaveTextContent("Administración");
    expect(brand).not.toHaveTextContent(/gestión/i);
  });

  test("usa símbolos de marca y deja WhatsApp como botón sin texto visible", () => {
    render(<SiteFooter
      socialLinks={{
        instagram_url: "https://instagram.com/mycdigitalizacion",
        facebook_url: "https://facebook.com/mycdigitalizacion",
        tiktok_url: "",
        youtube_url: "",
        linkedin_url: "",
      }}
      whatsapp={{ enabled: true, number: "5491155551234", message: "Hola" }}
    />);

    expect(screen.getByRole("link", { name: "Instagram" }).querySelector("svg")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Facebook" }).querySelector("svg")).not.toBeNull();
    const whatsapp = screen.getByRole("link", { name: "Consultar por WhatsApp" });
    expect(whatsapp.querySelector("svg")).not.toBeNull();
    expect(whatsapp).not.toHaveTextContent("Consultar");
  });

  test("el footer usa el mismo logo configurado para la tienda", () => {
    render(
      <BrandProvider branding={{ ...FALLBACK_BRANDING, logo_url: "/media/branding/logo-configurado.png" }}>
        <SiteFooter />
      </BrandProvider>,
    );

    expect(screen.getByRole("img", { name: "Logo de mycdigitalizacion" })).toHaveAttribute(
      "src",
      "/media/branding/logo-configurado.png",
    );
  });

  test("muestra el sello Sectigo en un documento aislado del storefront", () => {
    render(<SiteFooter />);

    expect(screen.getByTitle("Certificado SSL Sectigo")).toHaveAttribute(
      "src",
      "/sectigo-trust-seal.html",
    );
  });

  test("incluye la firma de Devlink con un enlace externo seguro", () => {
    render(<SiteFooter />);

    const devlink = screen.getByRole("link", { name: "Visitar el sitio web de Devlink" });
    expect(devlink).toHaveTextContent("Powered by Devlink");
    expect(devlink).toHaveAttribute("href", "https://devlink.com.ar/");
    expect(devlink).toHaveAttribute("target", "_blank");
    expect(devlink).toHaveAttribute("rel", "noreferrer noopener");
  });
});
