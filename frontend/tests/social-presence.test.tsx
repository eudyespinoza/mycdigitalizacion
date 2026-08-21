import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { SiteFooter } from "@/components/layout/site-footer";


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
});
