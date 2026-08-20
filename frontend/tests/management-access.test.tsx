import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ManagementAuditTable } from "@/components/management/audit-table";
import { ManagementUserEditor } from "@/components/management/user-editor";
import { ManagementUserTable } from "@/components/management/user-table";


describe("usuarios, roles y auditoría", () => {
  test("lista usuarios internos con roles y estado", () => {
    render(<ManagementUserTable users={[{
      id: 8,
      email: "catalogo@example.test",
      first_name: "Carla",
      last_name: "Catálogo",
      is_active: true,
      is_superuser: false,
      role_names: ["Catalog"],
      last_login: null,
    }]} />);
    expect(screen.getByText("Carla Catálogo")).toBeVisible();
    expect(screen.getByText("Catálogo")).toBeVisible();
    expect(screen.queryByText(/django/i)).not.toBeInTheDocument();
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
