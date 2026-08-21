import { serverGet } from "@/lib/api";
import type { StorefrontHome, StorefrontSettings } from "@/lib/types";

export const FALLBACK_BRANDING: StorefrontSettings = {
  public_name: "mycdigitalizacion", announcement: "", contact_email: "",
  pickup_enabled: true, pickup_label: "Retiro", pickup_address: "", pickup_hours: "",
  instagram_url: "", facebook_url: "", tiktok_url: "", youtube_url: "", linkedin_url: "",
  whatsapp_enabled: false, whatsapp_number: "", whatsapp_message: "",
  logo_url: "/brand/mycdigitalizacion-logo.png", logo_responsive_sources: [],
  favicon_url: "/brand/mycdigitalizacion-logo.png",
};

export async function loadStorefrontBranding() {
  try { return (await serverGet<StorefrontHome>("/storefront/home/")).settings; }
  catch { return FALLBACK_BRANDING; }
}
