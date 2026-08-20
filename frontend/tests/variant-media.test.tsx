import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import ProductPage from "@/app/producto/[slug]/page";
import { ProductCard } from "@/components/product/product-card";
import { serverGet } from "@/lib/api";
import type { Product } from "@/lib/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, serverGet: vi.fn() };
});

const product: Product = {
  id: 1,
  name: "Mochila urbana",
  slug: "mochila-urbana",
  description: "Mochila de uso diario",
  category: { id: 1, name: "Mochilas", slug: "mochilas", parent_id: null },
  brand: null,
  available_stock: 4,
  effective_price: "35000.00",
  on_offer: false,
  variants: [
    { id: 11, sku: "MOC-AZ", name: "Azul", price: "35000.00", available_stock: 2, attributes: [], pricing: { list_price: "35000.00", effective_price: "35000.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false }, packaged_weight_grams: 800, length_cm: "45.00", width_cm: "30.00", height_cm: "18.00", volume_cm3: "24300.000000" },
    { id: 12, sku: "MOC-RO", name: "Rosa", price: "35000.00", available_stock: 2, attributes: [], pricing: { list_price: "35000.00", effective_price: "35000.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false }, packaged_weight_grams: 800, length_cm: "45.00", width_cm: "30.00", height_cm: "18.00", volume_cm3: "24300.000000" },
  ],
  media: [
    { file: "/media/catalog/general.png", alt_text: "Vista general", order: 0, variant_id: null, variant_name: "" },
    { file: "/media/catalog/azul.png", alt_text: "Mochila azul", order: 1, variant_id: 11, variant_name: "Azul" },
    { file: "/media/catalog/rosa.png", alt_text: "Mochila rosa", order: 2, variant_id: 12, variant_name: "Rosa" },
  ],
};

describe("galería por variante", () => {
  beforeEach(() => {
    vi.mocked(serverGet).mockImplementation(async (path) => path === "/categories/" ? [] : product);
  });

  test("combina imágenes generales con la variante elegida", async () => {
    render(await ProductPage({ params: Promise.resolve({ slug: product.slug }) }));

    expect(screen.getByAltText("Vista general")).toBeVisible();
    expect(screen.getByAltText("Mochila azul")).toBeVisible();
    expect(screen.queryByAltText("Mochila rosa")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Opción"), { target: { value: "12" } });
    await waitFor(() => expect(screen.getByAltText("Mochila rosa")).toBeVisible());
    expect(screen.queryByAltText("Mochila azul")).not.toBeInTheDocument();
  });

  test("usa una imagen general como portada del catálogo", () => {
    render(<ProductCard product={{
      ...product,
      media: [
        { ...product.media[1], order: 0 },
        { ...product.media[0], order: 5 },
      ],
    }} />);
    expect(screen.getByAltText("Vista general")).toBeVisible();
    expect(screen.queryByAltText("Mochila azul")).not.toBeInTheDocument();
  });
});
