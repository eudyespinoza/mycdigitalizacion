"use client";

import { managementRequest } from "@/lib/management/api";
import type { ShippingBox } from "@/lib/management/operations-types";
import { ShippingBoxPanel } from "@/components/management/shipping-box-panel";


export function ManagementShippingPanel({ boxes }: { boxes: ShippingBox[] }) {
  return <ShippingBoxPanel boxes={boxes} onCreate={async (payload) => { await managementRequest("/shipping/boxes/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }} />;
}
