"use client";

import { IntegrationEditor } from "@/components/management/integration-editor";
import { managementRequest } from "@/lib/management/api";
import type { IntegrationConfiguration, IntegrationUpdate } from "@/lib/management/types";


export function IntegrationPanel({ integration }: { integration: IntegrationConfiguration }) {
  return (
    <IntegrationEditor
      integration={integration}
      onSave={(payload: IntegrationUpdate) =>
        managementRequest<IntegrationConfiguration>(`/integrations/${integration.provider}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        })}
      onTest={() =>
        managementRequest<IntegrationConfiguration>(`/integrations/${integration.provider}/test/`, {
          method: "POST",
        })}
    />
  );
}
