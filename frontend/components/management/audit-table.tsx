import type { ManagementAuditEvent } from "@/lib/management/access-types";


const actionLabels: Record<string, string> = {
  "integration.updated": "Integración actualizada",
  "settings.updated": "Configuración actualizada",
  "product.created": "Producto creado",
  "product.updated": "Producto actualizado",
  "inventory.adjusted": "Stock ajustado",
  "package_box.created": "Embalaje creado",
  "package_box.updated": "Embalaje actualizado",
  "content.created": "Contenido creado",
  "content.updated": "Contenido actualizado",
  "promotion.created": "Promoción creada",
  "promotion.updated": "Promoción actualizada",
  "staff.created": "Usuario interno creado",
  "staff.updated": "Usuario interno actualizado",
};


export function ManagementAuditTable({ events }: { events: ManagementAuditEvent[] }) {
  if (!events.length) return <div className="management-empty"><h2>No hay movimientos</h2><p>Las acciones administrativas aparecerán acá.</p></div>;
  return <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Acción</th><th>Usuario</th><th>Recurso</th><th>Fecha</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td><strong>{actionLabels[event.action] ?? event.action.replaceAll(".", " ")}</strong></td><td>{event.actor}</td><td>{event.resource} · {event.object_reference}</td><td>{new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(new Date(event.created_at))}</td></tr>)}</tbody></table></div>;
}
