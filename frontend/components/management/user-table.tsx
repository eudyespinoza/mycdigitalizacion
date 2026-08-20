import type { ManagementStaffUser } from "@/lib/management/access-types";


const roleLabels: Record<string, string> = {
  Owner: "Propietario",
  Catalog: "Catálogo",
  "Orders/Logistics": "Pedidos y logística",
  Content: "Contenido",
};


export function ManagementUserTable({ users }: { users: ManagementStaffUser[] }) {
  return <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Usuario</th><th>Roles</th><th>Estado</th><th>Último ingreso</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><strong>{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.email}</strong><small>{user.email}</small></td><td>{user.is_superuser ? <span className="management-pill is-live">Propietario</span> : user.role_names.map((role) => <span className="management-pill is-draft" key={role}>{roleLabels[role] ?? role}</span>)}</td><td><span className={`management-pill ${user.is_active ? "is-live" : "is-draft"}`}>{user.is_active ? "Activo" : "Deshabilitado"}</span></td><td>{user.last_login ? new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(new Date(user.last_login)) : "Todavía no ingresó"}</td></tr>)}</tbody></table></div>;
}
