export type ManagementUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  permissions: string[];
};

export type ManagementSession = { user: ManagementUser };

export type ManagementDashboard = {
  metrics: {
    active_products: number;
    low_stock_variants: number;
    orders_requiring_attention: number;
    integration_incidents: number;
  };
};

export type IntegrationProvider =
  | "mercadopago"
  | "correo_argentino"
  | "sid_renaper"
  | "smtp"
  | "geolocation"
  | "backups";

export type IntegrationStatus = "configured" | "incomplete" | "error" | "disabled";

export type IntegrationConfiguration = {
  provider: IntegrationProvider;
  label: string;
  enabled: boolean;
  environment: "sandbox" | "qa" | "production";
  status: IntegrationStatus;
  public_config: Record<string, string | number | boolean>;
  secret_fields: Record<string, boolean>;
  version: number;
  updated_at: string | null;
  updated_by: string;
  last_test_status: string;
  last_tested_at: string | null;
  last_test_message: string;
};

export type IntegrationUpdate = {
  enabled?: boolean;
  environment?: "sandbox" | "qa" | "production";
  public_config?: Record<string, string | number | boolean>;
  secrets?: Record<string, string>;
  clear_secret_fields?: string[];
};

export type GeneralSettings = {
  public_name: string;
  announcement: string;
  contact_email: string;
  pickup_enabled: boolean;
  pickup_label: string;
  pickup_address: string;
  pickup_hours: string;
  instagram_url: string;
  facebook_url: string;
  tiktok_url: string;
  youtube_url: string;
  linkedin_url: string;
  whatsapp_enabled: boolean;
  whatsapp_number: string;
  whatsapp_message: string;
  logo_url?: string;
  favicon_url?: string;
};
