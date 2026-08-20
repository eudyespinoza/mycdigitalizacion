export type ScheduledContent = {
  id: number;
  title: string;
  body?: string;
  alt_text: string;
  desktop_image_url: string;
  mobile_image_url: string;
  cta_label: string;
  cta_url: string;
  focal_x: number;
  focal_y: number;
  safe_height_mobile: number;
  safe_height_tablet: number;
  safe_height_desktop: number;
  starts_at: string | null;
  ends_at: string | null;
  order: number;
};

export type LandingCollection = ScheduledContent & { product_ids: number[] };
export type StorefrontHome = {
  settings: { public_name: string; announcement: string; contact_email: string };
  hero_slides: ScheduledContent[];
  promotion_slides: ScheduledContent[];
  collections: LandingCollection[];
  promotion_popups: ScheduledContent[];
};

export type Category = { id: number; name: string; slug: string; parent_id: number | null };
export type ProductMedia = { file: string; alt_text: string; order: number };
export type ProductVariant = {
  id: number;
  sku: string;
  name: string;
  price: string;
  packaged_weight_grams: number;
  length_cm: string;
  width_cm: string;
  height_cm: string;
  volume_cm3: string;
};
export type Product = {
  id: number;
  name: string;
  slug: string;
  description: string;
  category: Category;
  variants: ProductVariant[];
  media: ProductMedia[];
};

export type Cart = {
  lines: Array<{ id: number; variant_id: number; sku: string; quantity: number; unit_price: string }>;
  subtotal: string;
  discount: string;
  total: string;
  cart_token: string | null;
  coupon: string | null;
};
export type Customer = {
  id: number;
  email: string;
  email_verified_at: string | null;
  profile: { first_name: string; last_name: string; phone: string };
  masked_dni: string;
  masked_cuit: string;
};
export type BillingProfile = {
  id: number;
  label: string;
  legal_name: string;
  tax_condition: string;
  is_default: boolean;
  masked_cuit: string;
};
export type Address = {
  id: number;
  label: string;
  raw_address: string;
  normalized_address: string;
  street: string;
  number: string;
  postal_code: string;
  cpa: string;
  locality: string;
  province: string;
  latitude: string | null;
  longitude: string | null;
  floor: string;
  apartment: string;
  reference: string;
  notes: string;
  geocode_source: string;
  geocode_confidence: string | null;
  geocode_summary: Record<string, unknown>;
  needs_review: boolean;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};
export type ShippingQuote = {
  public_id: string;
  service: string;
  parcels: unknown[];
  base_amount: string;
  surcharge_amount: string;
  total_amount: string;
  currency: string;
  expires_at: string;
};
export type CheckoutResponse = {
  order_id: string;
  identity_status: string;
  payment_status: string;
  checkout_url: string;
};
export type Order = {
  public_id: string;
  identity_status: string;
  payment_status: string;
  fulfillment_status: string;
  fulfillment_method: string;
  customer_snapshot: Record<string, unknown>;
  address_snapshot: Record<string, unknown>;
  fiscal_snapshot: BillingProfile;
  coupon_code_snapshot: string;
  subtotal_snapshot: string;
  discount_snapshot: string;
  shipping_amount_snapshot: string;
  total_snapshot: string;
  items: Array<{
    product_name_snapshot: string;
    variant_name_snapshot: string;
    sku_snapshot: string;
    quantity: number;
    unit_price_snapshot: string;
    discount_snapshot: string;
    line_total_snapshot: string;
  }>;
  created_at: string;
};
