import Link from "next/link";

import { integrationFields } from "@/lib/management/integration-fields";
import type { IntegrationConfiguration, IntegrationStatus } from "@/lib/management/types";


const statusCopy: Record<IntegrationStatus, string> = {
  configured: "Configurada",
  incomplete: "Incompleta",
  error: "Con error",
  disabled: "Deshabilitada",
};


export function IntegrationOverview({
  integrations,
}: {
  integrations: IntegrationConfiguration[];
}) {
  return (
    <div className="integration-grid">
      {integrations.map((integration) => (
        <Link
          className="integration-card"
          href={`/gestion/integraciones/${integration.provider}`}
          key={integration.provider}
        >
          <div className="integration-card-heading">
            <h2>{integration.label}</h2>
            <span className={`integration-status status-${integration.status}`}>
              {statusCopy[integration.status]}
            </span>
          </div>
          <p>{integrationFields[integration.provider].description}</p>
          <small>
            {integration.updated_at
              ? `Actualizada por ${integration.updated_by || "el equipo"}`
              : "Todavía no configurada"}
          </small>
        </Link>
      ))}
    </div>
  );
}
