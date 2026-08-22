import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ManagementAuditTable } from "@/components/management/audit-table";
import { ManagementUserEditor } from "@/components/management/user-editor";
import { UserManagementPanel } from "@/components/management/user-management-panel";
import { ManagementUserTable } from "@/components/management/user-table";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const { managementRequest } = vi.hoisted(() => ({ managementRequest: vi.fn() }));

vi.mock("@/lib/management/api", () => ({ managementRequest }));

const role = { name: "Catalog", label: "Catálogo", permission_count: 7 };
const staffUser = {
  id: 8,
  email: "catalogo@example.test",
  first_name: "Carla",
  last_name: "Catálogo",
  is_active: true,
  is_superuser: false,
  role_names: ["Catalog"],
  last_login: null,
};


describe("usuarios, roles y auditoría", () => {
  beforeEach(() => {
    managementRequest.mockReset();
  });

  test("lista usuarios internos con roles y estado", () => {
    const { container } = render(<ManagementUserTable users={[{
      ...staffUser,
      last_login: "2026-08-20T10:00:00Z",
    }]} />);
    expect(screen.getByText("Carla Catálogo")).toBeVisible();
    expect(screen.getByText("Catálogo")).toBeVisible();
    expect(screen.queryByText(/django/i)).not.toBeInTheDocument();
    expect(container.querySelector("tbody tr")?.textContent).not.toMatch(/[\u00a0\u202f]/);
  });

  test("crea un usuario con contraseña y rol explícito", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ManagementUserEditor onSave={onSave} roles={[{ name: "Catalog", label: "Catálogo", permission_count: 7 }]} />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "catalogo@example.test" } });
    fireEvent.change(screen.getByLabelText("Contraseña temporal"), { target: { value: "StrongPassword!2026" } });
    fireEvent.click(screen.getByLabelText("Catálogo"));
    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      email: "catalogo@example.test",
      role_names: ["Catalog"],
    })));
  });

  test("mantiene el alta cerrada hasta que el administrador la solicita", async () => {
    managementRequest.mockResolvedValueOnce({
      ...staffUser,
      id: 9,
      email: "nuevo@example.test",
      first_name: "Nicolás",
    });
    render(<UserManagementPanel roles={[role]} users={[staffUser]} />);

    expect(screen.queryByRole("dialog", { name: "Nuevo usuario" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Agregar usuario" }));

    const dialog = screen.getByRole("dialog", { name: "Nuevo usuario" });
    fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "nuevo@example.test" } });
    fireEvent.change(within(dialog).getByLabelText("Nombre"), { target: { value: "Nicolás" } });
    fireEvent.change(within(dialog).getByLabelText("Contraseña temporal"), { target: { value: "StrongPassword!2026" } });
    fireEvent.click(within(dialog).getByLabelText("Catálogo"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Nuevo usuario" })).not.toBeInTheDocument());
    expect(screen.getByText("nuevo@example.test")).toBeVisible();
  });

  test("modifica los datos y permisos de un usuario existente", async () => {
    managementRequest.mockResolvedValueOnce({
      ...staffUser,
      first_name: "Carolina",
      role_names: [],
    });
    render(<UserManagementPanel roles={[role]} users={[staffUser]} />);

    fireEvent.click(screen.getByRole("button", { name: "Editar Carla Catálogo" }));
    const dialog = screen.getByRole("dialog", { name: "Editar usuario" });
    expect(within(dialog).getByLabelText("Email")).toHaveValue("catalogo@example.test");
    expect(within(dialog).getByLabelText("Catálogo")).toBeChecked();
    expect(within(dialog).getByLabelText("Nueva contraseña (opcional)")).not.toBeRequired();
    fireEvent.change(within(dialog).getByLabelText("Nombre"), { target: { value: "Carolina" } });
    fireEvent.click(within(dialog).getByLabelText("Catálogo"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(screen.getByText("Carolina Catálogo")).toBeVisible());
    expect(managementRequest).toHaveBeenCalledWith("/users/8/", expect.objectContaining({ method: "PATCH" }));
    expect(screen.queryByRole("dialog", { name: "Editar usuario" })).not.toBeInTheDocument();
  });

  test("da de baja y permite reactivar un usuario sin borrarlo", async () => {
    managementRequest
      .mockResolvedValueOnce({ ...staffUser, is_active: false })
      .mockResolvedValueOnce({ ...staffUser, is_active: true });
    render(<UserManagementPanel roles={[role]} users={[staffUser]} />);

    fireEvent.click(screen.getByRole("button", { name: "Dar de baja a Carla Catálogo" }));
    const confirmation = screen.getByRole("dialog", { name: "Dar de baja al usuario" });
    fireEvent.click(within(confirmation).getByRole("button", { name: "Dar de baja" }));

    await waitFor(() => expect(screen.getByText("Deshabilitado")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Reactivar a Carla Catálogo" }));
    await waitFor(() => expect(screen.getByText("Activo")).toBeVisible());
    expect(managementRequest).toHaveBeenNthCalledWith(1, "/users/8/", expect.objectContaining({ method: "PATCH" }));
    expect(managementRequest).toHaveBeenNthCalledWith(2, "/users/8/", expect.objectContaining({ method: "PATCH" }));
  });

  test("muestra auditoría entendible sin datos secretos", () => {
    render(<ManagementAuditTable events={[{
      id: 1,
      actor: "owner@example.test",
      action: "integration.updated",
      resource: "integration",
      object_reference: "mercadopago",
      metadata: { enabled: true },
      created_at: "2026-08-20T12:00:00Z",
    }]} />);
    expect(screen.getByText("Integración actualizada")).toBeVisible();
    expect(screen.getByText("owner@example.test")).toBeVisible();
    expect(screen.queryByText(/access_token|webhook_secret/i)).not.toBeInTheDocument();
  });
});
