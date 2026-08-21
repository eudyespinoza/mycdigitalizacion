import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { CampaignImage } from "@/components/home/campaign-image";
import { resolveCollectionProducts } from "@/lib/campaign-presentation";
import type { CatalogResponse, Product, ScheduledContent } from "@/lib/types";

const product = (id: number): Product => ({
  id, name: `Producto ${id}`, slug: `producto-${id}`, description: "",
  category: { id: 1, name: "Papelería", slug: "papeleria", parent_id: null },
  brand: null, available_stock: 1, is_available: true, effective_price: "100.00", on_offer: false,
  variants: [], media: [],
});
const facets: CatalogResponse["facets"] = { categories: [], brands: [], price: { min: null, max: null }, availability: { in_stock: 0, out_of_stock: 0 }, offer: { on_offer: 0, regular: 0 }, attributes: [] };

describe("Fix Round 2 CMS behavior", () => {
  test("responsive campaign media uses one prioritized image with authored mobile art direction and focal position", () => {
    const content: ScheduledContent = {
      id: 7, title: "Colección", body: "", alt_text: "Útiles sobre un escritorio",
      desktop_image_url: "/media/cms/desktop.png", mobile_image_url: "/media/cms/mobile.png",
      desktop_responsive_sources: [], mobile_responsive_sources: [],
      cta_label: "Ver", cta_url: "/catalogo", focal_x: "63", focal_y: "42",
      safe_height_mobile: 320, safe_height_tablet: 460, safe_height_desktop: 580,
      starts_at: null, ends_at: null, order: 1,
    };
    const { container } = render(<CampaignImage content={content} prefix="hero" priority />);
    const image = screen.getByRole("img", { name: content.alt_text });
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(container.querySelectorAll("picture source")).toHaveLength(1);
    expect(container.querySelector("picture")).toHaveStyle({ position: "absolute", inset: "0" });
    expect(container.querySelector("picture source")).toHaveAttribute("srcset", expect.stringContaining("mobile.png"));
    expect(image).toHaveAttribute("src", expect.stringContaining("desktop.png"));
    expect(image).toHaveAttribute("fetchpriority", "high");
    expect(image).toHaveAttribute("loading", "eager");
    expect(image).toHaveStyle({ objectPosition: "63% 42%" });
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
