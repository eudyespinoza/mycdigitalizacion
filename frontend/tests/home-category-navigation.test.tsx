import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import HomePage from "@/app/page";
import { FALLBACK_BRANDING } from "@/lib/branding";

const { serverGetMock } = vi.hoisted(() => ({ serverGetMock: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  serverGet: serverGetMock,
}));

describe("navegación de categorías del inicio", () => {
  beforeEach(() => {
    serverGetMock.mockImplementation((path: string) => {
      if (path === "/storefront/home/") {
        return Promise.resolve({
          settings: FALLBACK_BRANDING,
          hero_slides: [],
          promotion_slides: [],
          collections: [],
          promotion_popups: [],
        });
      }
      if (path === "/categories/") {
        return Promise.resolve([
          { id: 1, name: "Librería", slug: "libreria", parent_id: null },
        ]);
      }
      if (path.startsWith("/products/")) {
        return Promise.resolve({
          count: 0,
          next: null,
          previous: null,
          results: [],
          facets: {
            categories: [],
            brands: [],
            price: { min: null, max: null },
            availability: { in_stock: 0, out_of_stock: 0 },
            offer: { on_offer: 0, regular: 0 },
            attributes: [],
          },
        });
      }
      return Promise.reject(new Error(`Ruta inesperada: ${path}`));
    });
  });

  test("muestra cada categoría una sola vez en el menú superior", async () => {
    render(await HomePage());

    expect(screen.getAllByRole("link", { name: /librería/i })).toHaveLength(1);
    expect(document.querySelector(".category-rail")).not.toBeInTheDocument();
  });
});
