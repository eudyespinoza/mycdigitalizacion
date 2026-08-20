"use client";

import { createContext, useContext } from "react";
import { FALLBACK_BRANDING } from "@/lib/branding";
import type { StorefrontSettings } from "@/lib/types";

const BrandContext = createContext<StorefrontSettings>(FALLBACK_BRANDING);

export function BrandProvider({ branding, children }: { branding: StorefrontSettings; children: React.ReactNode }) {
  return <BrandContext.Provider value={branding}>{children}</BrandContext.Provider>;
}

export function useBranding() { return useContext(BrandContext); }
