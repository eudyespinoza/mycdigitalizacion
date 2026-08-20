import { notFound } from "next/navigation";
import Link from "next/link";

import { ContentEditorPanel } from "@/components/management/content-editor-panel";
import type { ContentKind, ManagedContent } from "@/lib/management/content-types";
import { managementServerGet } from "@/lib/management/server-api";


const kinds: ContentKind[] = ["hero", "promotions", "collections", "popups"];


export default async function EditContentPage({ params }: { params: Promise<{ kind: string; contentId: string }> }) {
  const { kind, contentId } = await params;
  if (!kinds.includes(kind as ContentKind)) notFound();
  const content = await managementServerGet<ManagedContent>(`/content/${kind}/${contentId}/`);
  return <div className="management-page management-editor-page"><Link className="management-back" href="/gestion/contenido">← Volver al contenido</Link><header className="management-page-header"><div><p className="management-kicker">Landing</p><h1>{content.title}</h1><p>Editá imagen, texto, vigencia, alturas y comportamiento.</p></div></header><ContentEditorPanel initial={content} kind={kind as ContentKind} /></div>;
}
