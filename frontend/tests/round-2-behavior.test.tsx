import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { CampaignImage } from "@/components/home/campaign-image";
import { resolveCollectionProducts } from "@/lib/campaign-presentation";
import type { CatalogResponse, Product, ScheduledContent } from "@/lib/types";

const product = (id: number): Product => ({
  id, name: `Producto ${id}`, slug: `producto-${id}`, description: "",
  category: { id: 1, name: "Papelería", slug: "papeleria", parent_id: null },
  brand: null, available_stock: 1, effective_price: "100.00", on_offer: false,
  variants: [], media: [],
});
const facets: CatalogResponse["facets"] = { categories: [], brands: [], price: { min: null, max: null }, availability: { in_stock: 0, out_of_stock: 0 }, offer: { on_offer: 0, regular: 0 }, attributes: [] };

describe("Fix Round 2 CMS behavior", () => {
  test("responsive campaign media renders authored desktop and mobile sources with focal position", () => {
    const content: ScheduledContent = {
      id: 7, title: "Colección", body: "", alt_text: "Útiles sobre un escritorio",
      desktop_image_url: "/media/cms/desktop.png", mobile_image_url: "/media/cms/mobile.png",
      cta_label: "Ver", cta_url: "/catalogo", focal_x: 63, focal_y: 42,
      safe_height_mobile: 320, safe_height_tablet: 460, safe_height_desktop: 580,
      starts_at: null, ends_at: null, order: 1,
    };
    render(<CampaignImage content={content} prefix="collection" />);
    const desktop = screen.getByRole("img", { name: content.alt_text });
    expect(desktop).toHaveAttribute("src", expect.stringContaining("desktop.png"));
    expect(desktop).toHaveStyle({ objectPosition: "63% 42%" });
    expect(document.querySelector(".collection-image-mobile")).toHaveAttribute("src", expect.stringContaining("mobile.png"));
  });

  test("collection product IDs resolve beyond the first server page without loading unnecessary pages", async () => {
    const pages: CatalogResponse[] = [
      { count: 3, next: "/api/v1/products/?page=2", previous: null, results: [product(1), product(2)], facets },
      { count: 3, next: null, previous: "/api/v1/products/?page=1", results: [product(99)], facets },
    ];
    const fetchPage = vi.fn(async (page: number) => pages[page - 1]);
    const result = await resolveCollectionProducts([99], pages[0], fetchPage);
    expect(result.map((item) => item.id)).toEqual([99]);
    expect(fetchPage).toHaveBeenCalledTimes(1);
    expect(fetchPage).toHaveBeenCalledWith(2);
  });
});
