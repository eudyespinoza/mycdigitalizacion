export type ContentKind = "hero" | "promotions" | "collections" | "popups";

export type ManagedContent = {
  id: number;
  title: string;
  body?: string;
  enabled: boolean;
  order: number;
  starts_at: string | null;
  ends_at: string | null;
  desktop_image_url: string;
  mobile_image_url: string;
  alt_text: string;
  cta_label: string;
  cta_url: string;
  focal_x: string;
  focal_y: string;
  safe_height_mobile: number;
  safe_height_tablet: number;
  safe_height_desktop: number;
  interval_ms?: number;
  pause_on_reduced_motion?: boolean;
  product_ids?: number[];
  frequency?: string;
  display_delay_ms?: number;
  dismissible?: boolean;
  version?: number;
};

export type ContentPayload = Omit<ManagedContent, "id" | "desktop_image_url" | "mobile_image_url"> & {
  desktop_image?: File;
  mobile_image?: File;
};

export type ManagedPromotionRule = {
  id: number;
  name: string;
  discount_type: "fixed" | "percentage";
  value: string;
  starts_at: string;
  ends_at: string;
  enabled: boolean;
  product_ids: number[];
  category_ids: number[];
};

export type ManagedCoupon = {
  id: number;
  code: string;
  discount_type: "fixed" | "percentage";
  value: string;
  starts_at: string;
  ends_at: string;
  enabled: boolean;
  combinable: boolean;
};
