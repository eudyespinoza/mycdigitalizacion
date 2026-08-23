import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { BrandProvider } from "@/components/layout/brand-provider";
import { SiteFooter } from "@/components/layout/site-footer";
import { FALLBACK_BRANDING } from "@/lib/branding";


describe("presencia social configurable", () => {
  test("muestra sólo redes configuradas y un WhatsApp habilitado", () => {
    render(
      <SiteFooter
        contactEmail="ventas@example.test"
        socialLinks={{
          instagram_url: "https://instagram.com/mycdigitalizacion",
          facebook_url: "",
          tiktok_url: "https://tiktok.com/@mycdigitalizacion",
          youtube_url: "",
          linkedin_url: "",
        }}
        whatsapp={{
          enabled: true,
          number: "5491155551234",
          message: "Hola, quiero consultar por un producto",
        }}
      />,
    );

    expect(screen.getByRole("link", { name: "Instagram" })).toHaveAttribute("href", "https://instagram.com/mycdigitalizacion");
    expect(screen.queryByRole("link", { name: "Facebook" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "TikTok" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Consultar por WhatsApp" })).toHaveAttribute(
      "href",
      "https://wa.me/5491155551234?text=Hola%2C%20quiero%20consultar%20por%20un%20producto",
    );
  });

  test("no muestra presencia social ni WhatsApp sin configuración", () => {
    render(
      <SiteFooter
        socialLinks={{ instagram_url: "", facebook_url: "", tiktok_url: "", youtube_url: "", linkedin_url: "" }}
        whatsapp={{ enabled: false, number: "", message: "" }}
      />,
    );

    expect(screen.queryByRole("navigation", { name: "Redes sociales" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Consultar por WhatsApp" })).not.toBeInTheDocument();
  });

  test("usa la configuración global en cualquier página pública", () => {
    render(
      <BrandProvider
        branding={{
          ...FALLBACK_BRANDING,
          public_name: "Tienda Demo",
          contact_email: "hola@tienda.test",
          instagram_url: "https://instagram.com/tienda-demo",
          whatsapp_enabled: true,
          whatsapp_number: "5491155559876",
          whatsapp_message: "Hola desde otra página",
        }}
      >
        <SiteFooter />
      </BrandProvider>,
    );

    expect(screen.getByText("Tienda Demo")).toBeVisible();
    expect(screen.getByRole("link", { name: "hola@tienda.test" })).toHaveAttribute(
      "href",
      "mailto:hola@tienda.test",
    );
    expect(screen.getByRole("link", { name: "Instagram" })).toHaveAttribute(
      "href",
      "https://instagram.com/tienda-demo",
    );
    expect(screen.getByRole("link", { name: "Consultar por WhatsApp" })).toHaveAttribute(
      "href",
      "https://wa.me/5491155559876?text=Hola%20desde%20otra%20p%C3%A1gina",
    );
  });

  test("organiza las rutas públicas en grupos útiles", () => {
    render(<SiteFooter />);

    expect(screen.getByRole("navigation", { name: "Comprar" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "Tu cuenta" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Direcciones" })).toHaveAttribute(
      "href",
      "/cuenta/direcciones",
    );
    expect(screen.getByRole("link", { name: "Datos de facturación" })).toHaveAttribute(
      "href",
      "/cuenta/fiscal",
    );
  });
});
