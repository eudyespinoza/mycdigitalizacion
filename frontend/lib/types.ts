export type ResponsiveMediaSource = { width: number; fallback: string; webp?: string; avif?: string };
export type ScheduledContent = {
  id: number; title: string; body?: string; alt_text: string;
  desktop_image_url: string; mobile_image_url: string;
  desktop_responsive_sources: ResponsiveMediaSource[]; mobile_responsive_sources: ResponsiveMediaSource[];
  cta_label: string; cta_url: string;
  focal_x: string; focal_y: string; safe_height_mobile: number; safe_height_tablet: number;
  safe_height_desktop: number; starts_at: string | null; ends_at: string | null; order: number;
};
export type TimedCampaign = ScheduledContent & { body: string; interval_ms: number; pause_on_reduced_motion: boolean };
export type CatalogContent = { slides: TimedCampaign[] };
export type PopupFrequency = "once_session" | "daily" | "weekly" | "always";
export type PromotionPopupContent = ScheduledContent & { body: string; frequency: PopupFrequency; display_delay_ms: number; dismissible: boolean; version: number };
export type LandingCollection = ScheduledContent & { product_ids: number[] };
export type StorefrontSettings = {
  public_name: string; announcement: string; contact_email: string;
  pickup_enabled: boolean; pickup_label: string; pickup_address: string; pickup_hours: string;
  instagram_url: string; facebook_url: string; tiktok_url: string; youtube_url: string; linkedin_url: string;
  whatsapp_enabled: boolean; whatsapp_number: string; whatsapp_message: string;
  theme_palette: "pulso" | "ocean" | "creative" | "natural" | "custom";
  theme_structure: string; theme_action: string; theme_wayfinding: string;
  theme_background: string; theme_text: string;
  logo_url: string; logo_responsive_sources: ResponsiveMediaSource[]; favicon_url: string;
};
export type StorefrontHome = {
  settings: StorefrontSettings;
  hero_slides: TimedCampaign[]; promotion_slides: TimedCampaign[];
  collections: LandingCollection[]; promotion_popups: PromotionPopupContent[];
};

export type Category = { id: number; name: string; slug: string; parent_id: number | null };
export type ProductMedia = {
  file: string;
  alt_text: string;
  order: number;
  variant_id: number | null;
  variant_name: string;
};
export type VariantAttribute = { name: string; slug: string; type: "text" | "integer" | "decimal" | "boolean" | "option"; value: string | number | boolean };
export type ProductVariant = {
  id: number; sku: string; name: string; price: string; available_stock: number;
  is_available: boolean; stock_is_infinite: boolean; purchase_limit: number | null;
  attributes: VariantAttribute[]; pricing: { list_price: string; effective_price: string; discount_amount: string; discount_percentage: string; on_offer: boolean };
  packaged_weight_grams: number; length_cm: string; width_cm: string; height_cm: string; volume_cm3: string;
};
export type Product = {
  id: number; name: string; slug: string; description: string; category: Category;
  brand: { name: string; slug: string } | null; available_stock: number; is_available: boolean; effective_price: string | null; on_offer: boolean;
  variants: ProductVariant[]; media: ProductMedia[];
};
export type FacetCategory = { name: string; slug: string; count: number; children: FacetCategory[] };
export type FacetAttribute = { name: string; slug: string; type: string; values: Array<{ value: string | number | boolean; label: string; count: number }> };
export type CatalogFacets = {
  categories: FacetCategory[];
  brands: Array<{ name: string; slug: string; count: number }>;
  price: { min: string | null; max: string | null };
  availability: { in_stock: number; out_of_stock: number };
  offer: { on_offer: number; regular: number };
  attributes: FacetAttribute[];
};
export type CatalogResponse = {
  count: number; next: string | null; previous: string | null; results: Product[]; facets: CatalogFacets;
};

export type CartLine = {
  id: number; variant_id: number; sku: string; product_name: string; variant_name: string; quantity: number; unit_price: string;
  line_subtotal: string; line_discount: string; line_total: string; availability: "available" | "insufficient_stock" | "unavailable"; available_stock: number;
  stock_is_infinite: boolean; purchase_limit: number | null;
  notices: Array<{ code: "price_changed" | "stock_changed"; previous: string | number; current: string | number }>;
};
export type Cart = {
  lines: CartLine[]; subtotal: string; discount: string; total: string;
  cart_token: string | null; coupon: string | null;
};
export type Customer = {
  id: number; email: string; email_verified_at: string | null; is_staff: boolean;
  profile: { first_name: string; last_name: string; phone: string };
  masked_dni: string; masked_cuit: string;
};
export type IdentityStatus = { status: string; can_validate?: boolean; detail?: string };
export type AuthConfiguration = {
  email_verification_required: boolean;
  google_enabled: boolean;
  google_client_id: string;
};
export type BillingProfile = { id: number; label: string; legal_name: string; tax_condition: string; is_default: boolean; masked_cuit: string };
export type Address = {
  id: number; label: string; raw_address: string; normalized_address: string; street: string; number: string;
  postal_code: string; cpa: string; locality: string; province: string; latitude: string | null;
  longitude: string | null; floor: string; apartment: string; reference: string; notes: string;
  geocode_source: string; geocode_confidence: string | null; geocode_summary: Record<string, unknown>;
  needs_review: boolean; reviewed_at: string | null; created_at: string; updated_at: string;
};
export type MapConfiguration = {
  provider: "openstreetmap" | "google_maps";
  google_maps_browser_key: string;
  google_maps_map_id: string;
};
export type ShippingQuote = {
  public_id: string; provider: string; provider_label: string; service: string; parcels: unknown[];
  base_amount: string; surcharge_amount: string; total_amount: string; amount_pending: boolean;
  currency: string; expires_at: string;
};
export type ShippingQuoteOptions = {
  results: ShippingQuote[];
  errors: Array<{ provider: string; label: string; code: string }>;
  manual_fallback: boolean;
};
export type CheckoutResponse = { order_id: string; identity_status: string; payment_status: string; checkout_url: string; shipping_cost_status: string };
export type TimelineEvent = { status: string; label: string; occurred_at: string | null };
export type ShipmentSummary = { carrier: string; tracking_number: string; status: string; updated_at: string };
export type PickupSummary = { enabled: boolean; label: string; address: string; hours: string };
export type Order = {
  public_id: string; identity_status: string; payment_status: string; fulfillment_status: string;
  fulfillment_method: string; customer_snapshot: Record<string, unknown>; address_snapshot: Record<string, unknown>;
  shipping_cost_status: string;
  fiscal_snapshot: BillingProfile; coupon_code_snapshot: string; subtotal_snapshot: string;
  discount_snapshot: string; shipping_amount_snapshot: string; total_snapshot: string;
  items: Array<{ product_name_snapshot: string; variant_name_snapshot: string; sku_snapshot: string; quantity: number; unit_price_snapshot: string; discount_snapshot: string; line_total_snapshot: string }>;
  timeline?: TimelineEvent[]; shipment?: ShipmentSummary | null; pickup_information?: PickupSummary | null;
  created_at: string;
};
