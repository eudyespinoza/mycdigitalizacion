export type ManagementCategory = {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  is_active: boolean;
};

export type ManagementBrand = { id: number; name: string; slug: string };

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
  }>;
};
