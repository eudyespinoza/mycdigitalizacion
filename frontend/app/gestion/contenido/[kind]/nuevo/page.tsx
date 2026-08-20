import { notFound } from "next/navigation";
import Link from "next/link";

import { ContentEditorPanel } from "@/components/management/content-editor-panel";
import type { ContentKind } from "@/lib/management/content-types";


const kinds: ContentKind[] = ["hero", "promotions", "collections", "popups"];


export default async function NewContentPage({ params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  if (!kinds.includes(kind as ContentKind)) notFound();
  return <div className="management-page management-editor-page"><Link className="management-back" href="/gestion/contenido">← Volver al contenido</Link><header className="management-page-header"><div><p className="management-kicker">Landing</p><h1>Nuevo contenido</h1><p>Configurá la campaña y sus variantes responsivas.</p></div></header><ContentEditorPanel kind={kind as ContentKind} /></div>;
}
