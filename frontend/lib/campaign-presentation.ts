import type { CSSProperties } from "react";
import type { CatalogResponse, Product } from "@/lib/types";

export function campaignHeightStyle(content: { safe_height_mobile: number; safe_height_tablet: number; safe_height_desktop: number }): CSSProperties {
  return {
    "--campaign-mobile-height": `${content.safe_height_mobile}px`,
    "--campaign-tablet-height": `${content.safe_height_tablet}px`,
    "--campaign-desktop-height": `${content.safe_height_desktop}px`,
  } as CSSProperties;
}

export async function resolveCollectionProducts(ids: number[], initial: CatalogResponse, fetchPage: (page: number) => Promise<CatalogResponse>): Promise<Product[]> {
  const found = new Map(initial.results.map((product) => [product.id, product]));
  let next = initial.next;
  let page = 2;
  while (next && ids.some((id) => !found.has(id))) {
    const response = await fetchPage(page);
    response.results.forEach((product) => found.set(product.id, product));
    next = response.next;
    page += 1;
  }
  return ids.map((id) => found.get(id)).filter((product): product is Product => Boolean(product));
}
