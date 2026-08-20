"use client";

import { GeneralSettingsForm } from "@/components/management/general-settings-form";
import { managementRequest } from "@/lib/management/api";
import type { GeneralSettings } from "@/lib/management/types";


export function GeneralSettingsPanel({ initial }: { initial: GeneralSettings }) {
  return (
    <GeneralSettingsForm
      initial={initial}
      onSave={async (settings) => {
        await managementRequest<GeneralSettings>("/settings/general/", {
          method: "PATCH",
          body: JSON.stringify(settings),
        });
      }}
    />
  );
}
