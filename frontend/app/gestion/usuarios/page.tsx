import { UserManagementPanel } from "@/components/management/user-management-panel";
import type { ManagementRole, ManagementStaffUser } from "@/lib/management/access-types";
import { managementServerGet } from "@/lib/management/server-api";


export default async function ManagementUsersPage() {
  const [users, roles] = await Promise.all([
    managementServerGet<{ results: ManagementStaffUser[] }>("/users/"),
    managementServerGet<{ results: ManagementRole[] }>("/roles/"),
  ]);
  return <div className="management-page"><header className="management-page-header"><div><p className="management-kicker">Equipo</p><h1>Usuarios y permisos</h1><p>Creá accesos internos y asigná sólo las funciones que cada persona necesita.</p></div></header><div className="management-content-gap"><UserManagementPanel roles={roles.results} users={users.results} /></div></div>;
}
