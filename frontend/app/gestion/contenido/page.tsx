import { ContentOverview } from "@/components/management/content-overview";
import type { ContentKind, ManagedContent } from "@/lib/management/content-types";
import { managementServerGet } from "@/lib/management/server-api";


export default async function ManagementContentPage() {
  const kinds: ContentKind[] = ["hero", "catalog", "promotions", "collections", "popups"];
  const responses = await Promise.all(kinds.map((kind) => managementServerGet<{ results: ManagedContent[] }>(`/content/${kind}/`)));
  const content = Object.fromEntries(kinds.map((kind, index) => [kind, responses[index].results])) as Record<ContentKind, ManagedContent[]>;
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Contenido</p><h1>Landing y catálogo</h1><p>Controlá campañas, carruseles, colecciones y avisos sin modificar código.</p></div><a className="button secondary" href="/?preview=gestion" rel="noreferrer" target="_blank">Ver tienda</a></header><div className="management-content-gap"><ContentOverview content={content} /></div></div>;
}
