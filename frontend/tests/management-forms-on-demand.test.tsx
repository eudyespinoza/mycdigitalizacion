import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { PromotionManagementPanel } from "@/components/management/promotion-management-panel";
import { ShippingBoxPanel } from "@/components/management/shipping-box-panel";
import { TaxonomyPanel } from "@/components/management/taxonomy-panel";

const { managementRequest } = vi.hoisted(() => ({ managementRequest: vi.fn() }));

vi.mock("@/lib/management/api", () => ({ managementRequest }));

describe("formularios de alta bajo demanda", () => {
  beforeEach(() => {
    managementRequest.mockReset();
  });

  test("promociones abre cada alta sólo desde su acción", () => {
    render(<PromotionManagementPanel coupons={[]} rules={[]} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nueva oferta automática" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nuevo cupón" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Nueva oferta" }));
    expect(screen.getByRole("dialog", { name: "Nueva oferta automática" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    fireEvent.click(screen.getByRole("button", { name: "Nuevo cupón" }));
    expect(screen.getByRole("dialog", { name: "Nuevo cupón" })).toBeVisible();
  });

  test("embalajes muestra el formulario sólo al agregar", () => {
    render(<ShippingBoxPanel boxes={[]} onCreate={vi.fn()} />);

    expect(screen.queryByRole("dialog", { name: "Nuevo embalaje" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Código")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Agregar embalaje" }));
    expect(screen.getByRole("dialog", { name: "Nuevo embalaje" })).toBeVisible();
    expect(screen.getByLabelText("Código")).toBeVisible();
  });

  test.each([
    ["Nueva categoría", "Nombre de la categoría"],
    ["Nueva marca", "Nombre de la marca"],
    ["Nuevo atributo", "Nombre del atributo"],
  ])("taxonomía abre %s sin mostrar otras altas", (action, field) => {
    render(<TaxonomyPanel initialAttributes={[]} initialBrands={[]} initialCategories={[]} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: action }));
    expect(screen.getByRole("dialog", { name: action })).toBeVisible();
    expect(screen.getByLabelText(field)).toBeVisible();
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
  });
});
