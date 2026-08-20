"use client";

import { InventoryTable } from "@/components/management/inventory-table";
import { managementRequest } from "@/lib/management/api";
import type { ManagementVariant } from "@/lib/management/catalog-types";


export function InventoryPanel({ variants }: { variants: ManagementVariant[] }) {
  return (
    <InventoryTable
      variants={variants}
      onAdjust={(id, new_on_hand, reason) => managementRequest<ManagementVariant>(
        `/variants/${id}/adjust-stock/`,
        { method: "POST", body: JSON.stringify({ new_on_hand, reason }) },
      )}
    />
  );
}
