export type ManagementCategory = {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  is_active: boolean;
};

export type ManagementBrand = { id: number; name: string; slug: string };

export type ManagementAttributeOption = { id: number; label: string; value: string };

export type ManagementAttributeDefinition = {
  id: number;
  name: string;
  slug: string;
  value_type: "text" | "integer" | "decimal" | "boolean" | "option";
  is_filterable: boolean;
  options: ManagementAttributeOption[];
};

export type ManagementAttributeValue = {
  definition_id: number;
  name: string;
  slug: string;
  value_type: ManagementAttributeDefinition["value_type"];
  value: string | number | boolean;
};

export type ManagementProductMedia = {
  id: number;
  file_url: string;
  responsive_sources: Array<Record<string, string | number>>;
  alt_text: string;
  order: number;
  variant_id: number | null;
  variant_name: string;
};

export type InventoryMovementSummary = {
  id: number;
  kind: string;
  quantity_delta: number;
  reference: string;
  source: string;
  actor: string | null;
  created_at: string;
};

export type ManagementVariant = {
  id: number;
  sku: string;
  name: string;
  price: string;
  cost: string;
  on_hand: number;
  available_stock: number;
  is_active: boolean;
  packaged_weight_grams: number;
  length_cm: string;
  width_cm: string;
  height_cm: string;
  recent_movements?: InventoryMovementSummary[];
  attributes: ManagementAttributeValue[];
};

export type ManagementProduct = {
  id: number;
  name: string;
  slug: string;
  description: string;
  category: ManagementCategory;
  brand: ManagementBrand | null;
  is_active: boolean;
  is_sellable: boolean;
  created_at: string;
  variants: ManagementVariant[];
  media: ManagementProductMedia[];
};

export type ProductEditorPayload = {
  name: string;
  slug: string;
  description: string;
  category_id: number;
  brand_id: number | null;
  publish: boolean;
  variants: Array<{
    id?: number;
    sku: string;
    name: string;
    price: string;
    cost: string;
    on_hand: number;
    is_active: boolean;
    packaged_weight_grams: number;
    length_cm: string;
    width_cm: string;
    height_cm: string;
    attribute_values?: Array<{ definition_id: number; value: string | number | boolean }>;
  }>;
};
