"use client";

import { useState } from "react";

import { ManagementUserEditor } from "@/components/management/user-editor";
import { ManagementUserTable } from "@/components/management/user-table";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { managementRequest } from "@/lib/management/api";
import type { ManagementRole, ManagementStaffUser } from "@/lib/management/access-types";


export function UserManagementPanel({ users, roles }: { users: ManagementStaffUser[]; roles: ManagementRole[] }) {
  const [rows, setRows] = useState(users);
  const [editor, setEditor] = useState<{ kind: "create" } | { kind: "edit"; user: ManagementStaffUser } | null>(null);
  const [statusTarget, setStatusTarget] = useState<ManagementStaffUser | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState("");

  async function saveUser(payload: Record<string, unknown>) {
    const editing = editor?.kind === "edit" ? editor.user : null;
    const saved = await managementRequest<ManagementStaffUser>(editing ? `/users/${editing.id}/` : "/users/", {
      method: editing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setRows((current) => editing
      ? current.map((row) => row.id === saved.id ? saved : row)
      : [...current, saved].sort((left, right) => left.email.localeCompare(right.email, "es")));
    setEditor(null);
  }

  async function setUserActive(user: ManagementStaffUser, isActive: boolean) {
    setStatusBusy(true);
    setStatusError("");
    try {
      const saved = await managementRequest<ManagementStaffUser>(`/users/${user.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      setRows((current) => current.map((row) => row.id === saved.id ? saved : row));
      setStatusTarget(null);
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "No pudimos cambiar el estado del usuario.");
    } finally {
      setStatusBusy(false);
    }
  }

  const editingUser = editor?.kind === "edit" ? editor.user : undefined;
  return (
    <section className="management-list-section">
      <div className="management-section-heading">
        <div><h2>Equipo</h2><p>Administrá accesos, roles y estado de cada cuenta interna.</p></div>
        <button className="button primary" onClick={() => setEditor({ kind: "create" })} type="button">Agregar usuario</button>
      </div>
      <ManagementUserTable
        onEdit={(user) => setEditor({ kind: "edit", user })}
        onToggleStatus={(user) => {
          if (user.is_active) {
            setStatusError("");
            setStatusTarget(user);
          } else {
            void setUserActive(user, true);
          }
        }}
        users={rows}
      />
      {statusError && !statusTarget ? <p className="inline-error" role="alert">{statusError}</p> : null}
      <ManagementFormDialog
        description={editingUser ? "Actualizá sus datos, permisos o contraseña." : "Creá un acceso interno con los permisos necesarios."}
        onClose={() => setEditor(null)}
        open={editor !== null}
        title={editingUser ? "Editar usuario" : "Nuevo usuario"}
      >
        <ManagementUserEditor
          initialValue={editingUser}
          key={editingUser ? `edit-${editingUser.id}` : "create"}
          onCancel={() => setEditor(null)}
          onSave={saveUser}
          roles={roles}
        />
      </ManagementFormDialog>
      <ConfirmationDialog
        busy={statusBusy}
        busyLabel="Desactivando…"
        confirmLabel="Dar de baja"
        description={statusTarget ? `${statusTarget.email} ya no podrá ingresar. Podrás reactivar la cuenta cuando lo necesites.` : ""}
        error={statusError}
        onCancel={() => {
          if (!statusBusy) setStatusTarget(null);
          setStatusError("");
        }}
        onConfirm={() => statusTarget ? setUserActive(statusTarget, false) : undefined}
        open={statusTarget !== null}
        title="Dar de baja al usuario"
      />
    </section>
  );
}
