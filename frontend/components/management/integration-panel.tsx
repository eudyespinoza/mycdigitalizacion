"use client";

import { IntegrationEditor } from "@/components/management/integration-editor";
import { MercadoPagoConnectPanel } from "@/components/management/mercadopago-connect-panel";
import { managementRequest } from "@/lib/management/api";
import type { IntegrationConfiguration, IntegrationUpdate } from "@/lib/management/types";


export function IntegrationPanel({
  integration,
  result,
}: {
  integration: IntegrationConfiguration;
  result?: string;
}) {
  if (integration.provider === "mercadopago") {
    return (
      <MercadoPagoConnectPanel
        integration={integration}
        onSave={(payload: IntegrationUpdate) =>
          managementRequest<IntegrationConfiguration>(`/integrations/${integration.provider}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })}
        onConnect={() =>
          managementRequest<IntegrationConfiguration>(
            "/integrations/mercadopago/connect/",
            { method: "POST" },
          )}
        onDisconnect={() =>
          managementRequest<IntegrationConfiguration>(
            "/integrations/mercadopago/oauth/disconnect/",
            { method: "POST" },
          )}
        onSyncPublicName={() =>
          managementRequest<IntegrationConfiguration>(
            "/integrations/mercadopago/sync-public-name/",
            { method: "POST" },
          )}
        result={result}
      />
    );
  }
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
