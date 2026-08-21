import Link from "next/link";

import { IntegrationPanel } from "@/components/management/integration-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { IntegrationConfiguration } from "@/lib/management/types";


export default async function IntegrationDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ provider: string }>;
  searchParams: Promise<{ mp_oauth?: string }>;
}) {
  const { provider } = await params;
  const { mp_oauth: oauthResult } = await searchParams;
  const integration = await managementServerGet<IntegrationConfiguration>(
    `/integrations/${provider}/`,
  );
  return (
    <div className="management-page management-editor-page">
      <Link className="management-back" href="/gestion/integraciones">← Integraciones</Link>
      <header className="management-page-header">
        <div>
          <p className="management-kicker">Integración</p>
          <h1>{integration.label}</h1>
        </div>
      </header>
      <IntegrationPanel integration={integration} result={oauthResult} />
    </div>
  );
}
