"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { trackAnalytics } from "@/lib/analytics/client";

const EXCLUDED_PREFIXES = ["/gestion", "/checkout", "/cuenta", "/ingresar", "/registro"];

export function AnalyticsTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const lastNavigation = useRef("");
  const search = searchParams.toString();

  useEffect(() => {
    if (!pathname || EXCLUDED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return;
    const navigation = `${pathname}?${search}`;
    if (lastNavigation.current === navigation) return;
    lastNavigation.current = navigation;
    const params = new URLSearchParams(search);
    const dimensions = {
      ...(params.get("utm_source") ? { utm_source: params.get("utm_source") ?? "" } : {}),
      ...(params.get("utm_medium") ? { utm_medium: params.get("utm_medium") ?? "" } : {}),
      ...(params.get("utm_campaign") ? { utm_campaign: params.get("utm_campaign") ?? "" } : {}),
      ...(document.referrer ? { referrer: document.referrer } : {}),
    };
    void trackAnalytics({ event_type: "page_view", path: pathname, dimensions });
  }, [pathname, search]);

  return null;
}
