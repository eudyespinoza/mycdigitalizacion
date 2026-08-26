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

const analyticsSession: ManagementSession = {
  ...session,
  user: {
    ...session.user,
    permissions: ["analytics.view_web_analytics", "analytics.view_commercial_analytics"],
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
    expect(document.querySelector('a[href^="/admin"]')).not.toBeInTheDocument();
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

  test("muestra cada tablero solo con su permiso explícito", () => {
    const { rerender } = render(
      <ManagementShell session={session}>
        <h1>Resumen</h1>
      </ManagementShell>,
    );

    expect(screen.queryByRole("link", { name: "Métricas web" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Compras y ventas" })).not.toBeInTheDocument();

    rerender(
      <ManagementShell session={analyticsSession}>
        <h1>Resumen</h1>
      </ManagementShell>,
    );

    expect(screen.getByRole("link", { name: "Métricas web" })).toHaveAttribute("href", "/gestion/metricas");
    expect(screen.getByRole("link", { name: "Compras y ventas" })).toHaveAttribute("href", "/gestion/estadisticas");
  });
});
