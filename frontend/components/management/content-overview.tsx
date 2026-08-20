import Link from "next/link";

import type { ContentKind, ManagedContent } from "@/lib/management/content-types";


const labels: Record<ContentKind, string> = { hero: "Hero principal", promotions: "Carrusel de promociones", collections: "Colecciones", popups: "Popup de promociones" };


export function ContentOverview({ content }: { content: Record<ContentKind, ManagedContent[]> }) {
  return <div className="management-content-sections">{(Object.keys(labels) as ContentKind[]).map((kind) => <section className="management-form-section" key={kind}><div className="management-section-heading"><div><p className="management-kicker">Landing</p><h2>{labels[kind]}</h2></div><Link className="button secondary" href={`/gestion/contenido/${kind}/nuevo`}>Agregar</Link></div>{content[kind].length ? <ul className="management-simple-list">{content[kind].map((item) => <li key={item.id}><span><strong>{item.title}</strong><small>{item.enabled ? "Visible" : "Deshabilitado"} · orden {item.order}</small></span><Link href={`/gestion/contenido/${kind}/${item.id}`}>Editar</Link></li>)}</ul> : <p>Todavía no hay contenido en este bloque.</p>}</section>)}</div>;
}
