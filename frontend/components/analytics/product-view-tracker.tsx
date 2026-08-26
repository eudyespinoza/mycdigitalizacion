"use client";

import { useEffect, useRef } from "react";

import { trackAnalytics } from "@/lib/analytics/client";

export function ProductViewTracker({ productId, path }: { productId: number; path: string }) {
  const tracked = useRef(false);

  useEffect(() => {
    if (tracked.current) return;
    tracked.current = true;
    void trackAnalytics({
      event_type: "product_view",
      product_id: productId,
      path,
    });
  }, [path, productId]);

  return null;
}
