import { GeneralSettingsPanel } from "@/components/management/general-settings-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { GeneralSettings } from "@/lib/management/types";


export default async function GeneralSettingsPage() {
  const settings = await managementServerGet<GeneralSettings>("/settings/general/");
  return (
    <div className="management-page management-editor-page">
      <header className="management-page-header">
        <div>
          <p className="management-kicker">Tienda</p>
          <h1>Configuración general</h1>
          <p>Datos visibles para clientes y condiciones del retiro.</p>
        </div>
      </header>
      <GeneralSettingsPanel initial={settings} />
    </div>
  );
}
