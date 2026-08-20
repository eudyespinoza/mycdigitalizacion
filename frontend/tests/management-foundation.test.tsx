import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { ManagementShell } from "@/components/management/management-shell";
import type { ManagementSession } from "@/lib/management/types";


const session: ManagementSession = {
  user: {
    id: 1,
    email: "admin@mycdigitalizacion.local",
    first_name: "Admin",
    last_name: "myc",
    is_staff: true,
    is_superuser: true,
    permissions: ["catalog.change_product"],
  },
};


describe("base del panel de gestión", () => {
  test("muestra navegación operativa sin enlazar Django Admin", () => {
    render(
      <ManagementShell session={session}>
        <h1>Resumen</h1>
      </ManagementShell>,
    );

    expect(screen.getByRole("link", { name: "Catálogo" })).toHaveAttribute(
      "href",
      "/gestion/catalogo",
    );
    expect(screen.getByRole("link", { name: "Integraciones" })).toHaveAttribute(
      "href",
      "/gestion/integraciones",
    );
    expect(screen.getByText("admin@mycdigitalizacion.local")).toBeVisible();
    expect(screen.queryByRole("link", { name: /django|admin/i })).not.toBeInTheDocument();
  });

  test("expone navegación completa en lenguaje de negocio", () => {
    render(
      <ManagementShell session={session}>
        <h1>Resumen</h1>
      </ManagementShell>,
    );

    for (const label of [
      "Inicio",
      "Catálogo",
      "Inventario",
      "Pedidos",
      "Clientes",
      "Contenido",
      "Promociones",
      "Envíos",
      "Integraciones",
      "Usuarios",
      "Auditoría",
      "Configuración",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeVisible();
    }
  });
});
