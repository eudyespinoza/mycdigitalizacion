import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import ManagementCustomerPage from "@/app/gestion/clientes/[customerId]/page";
import { managementRequest } from "@/lib/management/api";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementCustomerDetail } from "@/lib/management/operations-types";


vi.mock("@/lib/management/server-api", () => ({ managementServerGet: vi.fn() }));
vi.mock("@/lib/management/api", () => ({ managementRequest: vi.fn() }));


const customer: ManagementCustomerDetail = {
  id: 7,
  name: "Ana Pérez",
  first_name: "Ana",
  last_name: "Pérez",
  email: "cliente@example.test",
  phone: "1122334455",
  masked_dni: "••••3456",
  email_verified: true,
  order_count: 1,
  total_spent: "12500.00",
  addresses: [{
    id: 4,
    label: "Casa",
    raw_address: "Av. Siempre Viva 742",
    normalized_address: "Avenida Siempre Viva 742",
    street: "Avenida Siempre Viva",
    number: "742",
    postal_code: "1000",
    cpa: "C1000ABC",
    locality: "Ciudad Autónoma de Buenos Aires",
    province: "Ciudad Autónoma de Buenos Aires",
    floor: "4",
    apartment: "B",
    reference: "Portón azul",
    notes: "Llamar al llegar",
    needs_review: false,
  }],
  billing_profiles: [{
    id: 9,
    label: "Personal",
    legal_name: "Ana Pérez",
    tax_condition: "consumidor_final",
    masked_cuit: "••-••••••••-3",
    is_default: true,
  }],
  orders: [],
};


describe("ficha de cliente", () => {
  beforeEach(() => {
    vi.mocked(managementServerGet).mockResolvedValue(customer);
    vi.mocked(managementRequest).mockReset();
  });

  test("organiza los datos completos y mantiene la edición cerrada hasta solicitarla", async () => {
    render(await ManagementCustomerPage({ params: Promise.resolve({ customerId: "7" }) }));

    expect(screen.getByText("••••3456")).toBeVisible();
    expect(screen.getByText("Avenida Siempre Viva 742")).toBeVisible();
    expect(screen.getByText(/Piso 4 · Depto\. B/)).toBeVisible();
    expect(screen.getByText(/CP 1000/)).toBeVisible();
    expect(screen.getByText("Portón azul")).toBeVisible();
    expect(screen.getByText("••-••••••••-3")).toBeVisible();
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Editar cliente" }));

    const dialog = screen.getByRole("dialog", { name: "Editar cliente" });
    expect(within(dialog).getByLabelText("Nombre")).toHaveValue("Ana");
    expect(within(dialog).getByLabelText("Apellido")).toHaveValue("Pérez");
  });

  test("actualiza el contacto desde el formulario solicitado", async () => {
    vi.mocked(managementRequest).mockImplementation(async (_path, init) => {
      const payload = JSON.parse(String(init?.body));
      if (payload.first_name !== "Eudys" || payload.phone !== "1134567890") {
        throw new Error("Payload de contacto inválido");
      }
      return { ...customer, name: "Eudys Espinoza", first_name: "Eudys", last_name: "Espinoza", phone: "1134567890" };
    });
    render(await ManagementCustomerPage({ params: Promise.resolve({ customerId: "7" }) }));
    fireEvent.click(screen.getByRole("button", { name: "Editar cliente" }));
    const dialog = screen.getByRole("dialog", { name: "Editar cliente" });
    fireEvent.change(within(dialog).getByLabelText("Nombre"), { target: { value: "Eudys" } });
    fireEvent.change(within(dialog).getByLabelText("Apellido"), { target: { value: "Espinoza" } });
    fireEvent.change(within(dialog).getByLabelText("Teléfono"), { target: { value: "1134567890" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Eudys Espinoza" })).toBeVisible());
    expect(screen.queryByRole("dialog", { name: "Editar cliente" })).not.toBeInTheDocument();
  });

  test("edita un domicilio sin mostrar el formulario antes de solicitarlo", async () => {
    vi.mocked(managementRequest).mockImplementation(async (_path, init) => {
      const payload = JSON.parse(String(init?.body));
      if (payload.street !== "Avenida Corrientes" || payload.number !== "1550") {
        throw new Error("Payload de domicilio inválido");
      }
      return {
        ...customer.addresses[0],
        raw_address: "Avenida Corrientes 1550",
        normalized_address: "Avenida Corrientes 1550",
        street: "Avenida Corrientes",
        number: "1550",
      };
    });
    render(await ManagementCustomerPage({ params: Promise.resolve({ customerId: "7" }) }));
    expect(screen.queryByRole("dialog", { name: "Editar dirección" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Editar dirección Casa" }));
    const dialog = screen.getByRole("dialog", { name: "Editar dirección" });
    fireEvent.change(within(dialog).getByLabelText("Calle"), { target: { value: "Avenida Corrientes" } });
    fireEvent.change(within(dialog).getByLabelText("Altura"), { target: { value: "1550" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar dirección" }));

    await waitFor(() => expect(screen.getByText("Avenida Corrientes 1550")).toBeVisible());
    expect(screen.queryByRole("dialog", { name: "Editar dirección" })).not.toBeInTheDocument();
  });
});
