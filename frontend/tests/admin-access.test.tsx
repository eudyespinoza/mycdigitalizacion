import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { AccountDashboard } from "@/components/account/account-dashboard";
import { apiRequest } from "@/lib/api";
import type { Customer } from "@/lib/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiRequest: vi.fn() };
});

const customer: Customer & { is_staff: boolean } = {
  id: 7,
  email: "admin@mycdigitalizacion.local",
  email_verified_at: "2026-08-20T12:00:00Z",
  is_staff: true,
  profile: { first_name: "", last_name: "", phone: "" },
  masked_dni: "",
  masked_cuit: "",
};

describe("administrator account discovery", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_ADMIN_URL", "http://localhost:8000/admin/");
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path === "/customers/me/") return customer;
      return [];
    });
  });

  afterEach(() => vi.unstubAllEnvs());

  test("a staff customer can open the operational control panel from My account", async () => {
    render(<AccountDashboard />);

    const link = await screen.findByRole("link", { name: "Abrir panel de control" });
    expect(link).toHaveAttribute("href", "http://localhost:8000/admin/");
    expect(screen.getByText(/productos, contenido, pedidos e integraciones/i)).toBeVisible();
  });
});
