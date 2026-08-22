import type { ManagementStaffUser } from "@/lib/management/access-types";


const roleLabels: Record<string, string> = {
  Owner: "Propietario",
  Catalog: "Catálogo",
  "Orders/Logistics": "Pedidos y logística",
  Content: "Contenido",
};


type ManagementUserTableProps = {
  onEdit?: (user: ManagementStaffUser) => void;
  onToggleStatus?: (user: ManagementStaffUser) => void;
  users: ManagementStaffUser[];
};


function userLabel(user: ManagementStaffUser) {
  return [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email;
}


function lastLoginLabel(value: string | null) {
  if (!value) return "Todavía no ingresó";
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(value)).replace(/[\u00a0\u202f]/g, " ");
}


export function ManagementUserTable({ onEdit, onToggleStatus, users }: ManagementUserTableProps) {
  return (
    <div className="management-table-wrap">
      <table className="management-table">
        <thead><tr><th>Usuario</th><th>Roles</th><th>Estado</th><th>Último ingreso</th>{onEdit || onToggleStatus ? <th>Acciones</th> : null}</tr></thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td><strong>{userLabel(user)}</strong><small>{user.email}</small></td>
              <td className="management-role-cell">{user.is_superuser ? <span className="management-pill is-live">Propietario</span> : user.role_names.map((role) => <span className="management-pill is-draft" key={role}>{roleLabels[role] ?? role}</span>)}</td>
              <td><span className={`management-pill ${user.is_active ? "is-live" : "is-draft"}`}>{user.is_active ? "Activo" : "Deshabilitado"}</span></td>
              <td>{lastLoginLabel(user.last_login)}</td>
              {onEdit || onToggleStatus ? (
                <td>
                  <div className="management-content-actions">
                    {onEdit ? <button aria-label={`Editar ${userLabel(user)}`} className="button secondary" onClick={() => onEdit(user)} type="button">Editar</button> : null}
                    {onToggleStatus ? (
                      <button
                        aria-label={`${user.is_active ? "Dar de baja a" : "Reactivar a"} ${userLabel(user)}`}
                        className={`button ${user.is_active ? "danger" : "secondary"}`}
                        onClick={() => onToggleStatus(user)}
                        type="button"
                      >
                        {user.is_active ? "Dar de baja" : "Reactivar"}
                      </button>
                    ) : null}
                  </div>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
