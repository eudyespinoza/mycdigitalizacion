export type CatalogState = {
  q?: string;
  category?: string;
  brands?: string[];
  minPrice?: number;
  maxPrice?: number;
  inStock?: boolean;
  onOffer?: boolean;
  attributes?: Record<string, string[]>;
  sort?: "relevance" | "price_asc" | "price_desc" | "discount_desc" | "newest";
  page?: number;
};

export function buildCatalogQuery(state: CatalogState) {
  const rows: Array<[string, string]> = [];
  if (state.q) rows.push(["q", state.q]);
  if (state.category) rows.push(["category", state.category]);
  if (state.brands?.length) rows.push(["brand", state.brands.join(",")]);
  if (state.minPrice !== undefined) rows.push(["min_price", String(state.minPrice)]);
  if (state.maxPrice !== undefined) rows.push(["max_price", String(state.maxPrice)]);
  if (state.inStock) rows.push(["availability", "in_stock"]);
  if (state.onOffer) rows.push(["offer", "true"]);
  if (state.sort && state.sort !== "relevance") rows.push(["ordering", state.sort]);
  if (state.page && state.page !== 1) rows.push(["page", String(state.page)]);
  Object.entries(state.attributes ?? {}).forEach(([name, values]) => {
    if (values.length) rows.push([`attribute_${name}`, values.join(",")]);
  });
  rows.sort(([a], [b]) => a.localeCompare(b));
  const params = new URLSearchParams();
  rows.forEach(([key, value]) => params.set(key, value));
  return params.toString();
}
