"use client";

import { useRouter } from "next/navigation";

import { BrandingForm } from "@/components/management/branding-form";
import { managementRequest } from "@/lib/management/api";


export function BrandingPanel({ logoUrl, faviconUrl }: { logoUrl: string; faviconUrl: string }) {
  const router = useRouter();
  return <BrandingForm logoUrl={logoUrl} faviconUrl={faviconUrl} onSave={async (data) => {
    await managementRequest("/settings/general/", { method: "PATCH", body: data });
    router.refresh();
  }} />;
}
