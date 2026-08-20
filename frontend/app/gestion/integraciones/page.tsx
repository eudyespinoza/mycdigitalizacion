import { IntegrationOverview } from "@/components/management/integration-overview";
import { managementServerGet } from "@/lib/management/server-api";
import type { IntegrationConfiguration } from "@/lib/management/types";


export default async function IntegrationsPage() {
  const data = await managementServerGet<{ results: IntegrationConfiguration[] }>(
    "/integrations/",
  );
  return (
    <div className="management-page">
      <header className="management-page-header">
        <div>
          <p className="management-kicker">Configuración</p>
          <h1>Integraciones</h1>
          <p>Conectá pagos, envíos, identidad, correos, mapas y copias externas.</p>
        </div>
      </header>
      <IntegrationOverview integrations={data.results} />
    </div>
  );
}
