export type CatalogState = {
  q?: string;
  category?: string;
  sort?: "relevance" | "price_asc" | "price_desc";
  page?: number;
};

export function buildCatalogQuery(state: CatalogState) {
  const params = new URLSearchParams();
  Object.entries(state)
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([key, value]) => {
      if (value !== undefined && value !== "" && value !== "relevance" && value !== 1) {
        params.set(key, String(value));
      }
    });
  return params.toString();
}
