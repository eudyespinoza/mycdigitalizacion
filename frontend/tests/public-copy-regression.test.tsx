import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { CatalogBrowser } from "@/components/catalog/catalog-browser";
import { CheckoutStatePanel } from "@/components/checkout/checkout-flow";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductPurchase } from "@/components/product/product-purchase";
import { apiRequest } from "@/lib/api";
import type { CatalogResponse, ProductVariant } from "@/lib/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const facets: CatalogResponse["facets"] = {
  categories: [],
  brands: [],
  price: { min: null, max: null },
  availability: { in_stock: 0, out_of_stock: 0 },
  offer: { on_offer: 0, regular: 0 },
  attributes: [],
};

const variant: ProductVariant = {
  id: 11,
  sku: "CUA-A5-001",
  name: "Tapa azul",
  price: "4890.00",
  available_stock: 8,
  is_available: true,
  stock_is_infinite: false,
  purchase_limit: 8,
  attributes: [],
  pricing: { list_price: "4890.00", effective_price: "4890.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false },
  packaged_weight_grams: 300,
  length_cm: "21.00",
  width_cm: "15.00",
  height_cm: "2.00",
  volume_cm3: "630.000000",
};

describe("public storefront copy regression", () => {
  beforeEach(() => {
    push.mockReset();
    vi.restoreAllMocks();
  });

  test("catalog result count agrees in singular and plural", () => {
    const response = (count: number): CatalogResponse => ({ count, next: null, previous: null, results: [], facets });
    const { rerender } = render(<CatalogBrowser response={response(1)} categories={[]} initial={{}} />);
    expect(screen.getByText("producto encontrado").closest("p")).toHaveTextContent("1 producto encontrado");

    rerender(<CatalogBrowser response={response(2)} categories={[]} initial={{}} />);
    expect(screen.getByText("productos encontrados").closest("p")).toHaveTextContent("2 productos encontrados");
  });

  test("checkout, header and footer explain benefits without implementation jargon", () => {
    const { container } = render(<><SiteHeader categories={[]} /><CheckoutStatePanel state="provider_down" /><SiteFooter /></>);
    expect(document.body).not.toHaveTextContent(/servidor|api|proveedor|auditable|configurable/i);
    expect(screen.getByText(/guardamos tus datos/i)).toBeVisible();
    expect(container.querySelector(".brand-lockup-media")).toHaveClass("brand-lockup-fallback");
  });

  test("product options show customer choices without exposing internal SKU or server details", () => {
    render(<ProductPurchase productName="Cuaderno A5 rayado" variants={[variant]} onAdd={vi.fn()} />);
    expect(screen.getByRole("option", { name: "Tapa azul" })).toBeVisible();
    expect(document.body).not.toHaveTextContent(/CUA-A5-001|servidor/i);
  });

  test("network failures become a clear customer message", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(apiRequest("/addresses/")).rejects.toThrow("No pudimos conectarnos");
  });

  test("email verification errors are shown in Spanish", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Email verification is required" }), { status: 403 }));
    await expect(apiRequest("/customers/me/")).rejects.toThrow("Verificá tu email para continuar.");
  });
});
