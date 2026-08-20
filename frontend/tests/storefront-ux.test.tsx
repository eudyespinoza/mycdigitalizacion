import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { CheckoutStatePanel, getTrustedOrderState } from "@/components/checkout/checkout-flow";
import { Hero } from "@/components/home/hero";
import { PromotionPopup } from "@/components/home/promotion-popup";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductPurchase } from "@/components/product/product-purchase";
import { buildCatalogQuery } from "@/lib/catalog-query";
import { requiresReverseLookup } from "@/lib/geo";
import { validateVerificationCode } from "@/lib/validation";

describe("storefront behavior", () => {
  test("navigation exposes search, account, cart and a skip link", () => {
    render(<SiteHeader categories={[]} />);

    expect(screen.getByRole("link", { name: /saltar al contenido/i })).toHaveAttribute(
      "href",
      "#contenido",
    );
    expect(screen.getByRole("searchbox", { name: /buscar productos/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /mi cuenta/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /carrito/i })).toBeVisible();
  });

  test("hero renders scheduled CMS content without replacing it with claims", () => {
    render(
      <Hero
        slide={{
          id: 4,
          title: "Tu catálogo, a mano",
          body: "Encontrá productos para cada momento.",
          alt_text: "Cuadernos y accesorios sobre una mesa",
          desktop_image_url: "/campaigns/pulso-comercial-hero.png",
          mobile_image_url: "",
          desktop_responsive_sources: [],
          mobile_responsive_sources: [],
          cta_label: "Explorar catálogo",
          cta_url: "/catalogo",
          focal_x: "50",
          focal_y: "50",
          safe_height_mobile: 420,
          safe_height_tablet: 520,
          safe_height_desktop: 620,
          starts_at: null,
          ends_at: null,
          order: 1,
          interval_ms: 6_000,
          pause_on_reduced_motion: true,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Tu catálogo, a mano" })).toBeVisible();
    expect(screen.getByText("Encontrá productos para cada momento.")).toBeVisible();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Cuadernos y accesorios sobre una mesa",
    );
  });

  test("catalog filters remain shareable in the URL", () => {
    expect(
      buildCatalogQuery({ q: "cuaderno", category: "papeleria", sort: "price_asc", page: 2 }),
    ).toBe("category=papeleria&ordering=price_asc&page=2&q=cuaderno");
  });

  test("variant and quantity produce the authoritative cart request", async () => {
    const add = vi.fn();
    render(
      <ProductPurchase
        productName="Cuaderno"
        variants={[
          {
            id: 11,
            sku: "CUA-11",
            name: "Azul",
            price: "12500.00",
            available_stock: 8,
            attributes: [],
            pricing: { list_price: "12500.00", effective_price: "12500.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false },
            packaged_weight_grams: 300,
            length_cm: "21.00",
            width_cm: "15.00",
            height_cm: "2.00",
            volume_cm3: "630.000000",
          },
        ]}
        onAdd={add}
      />,
    );
    fireEvent.change(screen.getByLabelText(/cantidad/i), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /agregar al carrito/i }));
    await screen.findByRole("status");
    expect(add).toHaveBeenCalledWith({ variant_id: 11, quantity: 2 });
  });

  test("email verification accepts exactly six digits", () => {
    expect(validateVerificationCode("123456")).toBeNull();
    expect(validateVerificationCode("12345")).toMatch(/6 dígitos/i);
    expect(validateVerificationCode("12A456")).toMatch(/6 dígitos/i);
  });

  test("checkout provider outage explains recovery without fake success", () => {
    render(<CheckoutStatePanel state="provider_down" />);
    expect(screen.getByRole("heading", { name: /servicio no disponible/i })).toBeVisible();
    expect(screen.getByText(/intentá nuevamente/i)).toBeVisible();
    expect(screen.queryByText(/pago aprobado/i)).not.toBeInTheDocument();
  });

  test("promotion popup dismissal is remembered for its campaign", () => {
    const dismiss = vi.fn();
    render(
      <PromotionPopup
        campaignId={9}
        title="Beneficio vigente"
        body="Consultá las condiciones de la promoción."
        ctaLabel="Ver promoción"
        ctaUrl="/catalogo"
        dismissedCampaigns={[]}
        onDismiss={dismiss}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cerrar promoción/i }));
    expect(dismiss).toHaveBeenCalledWith(9);
  });

  test("a pin moved more than 150m requires reverse lookup confirmation", () => {
    expect(requiresReverseLookup(-34.6037, -58.3816, -34.604, -58.3818)).toBe(false);
    expect(requiresReverseLookup(-34.6037, -58.3816, -34.606, -58.3816)).toBe(true);
  });

  test("redirect query parameters never establish payment state", () => {
    expect(getTrustedOrderState(new URLSearchParams("status=approved"), null)).toBe("checking");
    expect(getTrustedOrderState(new URLSearchParams("status=rejected"), "paid")).toBe(
      "approved",
    );
  });
});
