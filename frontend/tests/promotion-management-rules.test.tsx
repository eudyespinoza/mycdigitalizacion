import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ManagementProductTable } from "@/components/management/product-table";
import { PromotionEditor } from "@/components/management/promotion-editor";
import { PromotionManagementPanel } from "@/components/management/promotion-management-panel";
import type { ManagementProduct } from "@/lib/management/catalog-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const productOptions = [
  { id: 11, label: "Cuaderno A5", description: "Cuadernos" },
  { id: 12, label: "Lapicera azul", description: "Escritura" },
];

const categoryOptions = [
  { id: 2, label: "Librería" },
  { id: 5, label: "Cuadernos" },
];

describe("reglas de promociones en gestión", () => {
  test("selecciona varios productos y categorías por nombre", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <PromotionEditor
        categoryOptions={categoryOptions}
        kind="rule"
        onSave={onSave}
        productOptions={productOptions}
      />,
    );

    const products = screen.getByRole("group", { name: "Productos incluidos" });
    fireEvent.click(within(products).getByRole("checkbox", { name: /Cuaderno A5/ }));
    fireEvent.click(within(products).getByRole("checkbox", { name: /Lapicera azul/ }));
    const categories = screen.getByRole("group", { name: "Categorías incluidas" });
    fireEvent.click(within(categories).getByRole("checkbox", { name: "Cuadernos" }));
    fireEvent.change(screen.getByLabelText("Nombre interno"), {
      target: { value: "Semana de escritura" },
    });
    fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar oferta" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      product_ids: [11, 12],
      category_ids: [5],
    })));
  });

  test("configura máximo de usos y limpia el formulario al guardar otro cupón", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<PromotionEditor kind="coupon" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("Código"), { target: { value: "LAPIZ10" } });
    fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Cantidad máxima de usos"), {
      target: { value: "40" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cupón" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      code: "LAPIZ10",
      max_redemptions: 40,
    })));
    expect(screen.getByLabelText("Código")).toHaveValue("");
    expect(screen.getByLabelText("Cantidad máxima de usos")).toHaveValue(null);
  });

  test("lista varias ofertas y cupones con su uso efectivo", () => {
    render(
      <PromotionManagementPanel
        categoryOptions={categoryOptions}
        productOptions={productOptions}
        rules={[
          { id: 1, name: "Oferta cuadernos", discount_type: "percentage", value: "15.00", starts_at: "2026-08-20T10:00:00Z", ends_at: "2026-08-27T10:00:00Z", enabled: true, product_ids: [11], category_ids: [] },
          { id: 2, name: "Oferta lapiceras", discount_type: "fixed", value: "500.00", starts_at: "2026-08-28T10:00:00Z", ends_at: "2026-09-02T10:00:00Z", enabled: true, product_ids: [12], category_ids: [] },
        ]}
        coupons={[
          { id: 3, code: "UNO10", discount_type: "percentage", value: "10.00", starts_at: "2026-08-20T10:00:00Z", ends_at: "2026-08-27T10:00:00Z", enabled: true, combinable: false, max_redemptions: 10, used_redemptions: 3, reserved_redemptions: 1 },
          { id: 4, code: "LIBRE5", discount_type: "fixed", value: "500.00", starts_at: "2026-08-20T10:00:00Z", ends_at: "2026-08-27T10:00:00Z", enabled: true, combinable: true, max_redemptions: null, used_redemptions: 8, reserved_redemptions: 0 },
        ]}
      />,
    );

    expect(screen.getByText("Oferta cuadernos")).toBeVisible();
    expect(screen.getByText("Oferta lapiceras")).toBeVisible();
    expect(screen.getByText("UNO10")).toBeVisible();
    expect(screen.getByText("LIBRE5")).toBeVisible();
    expect(screen.getByText(/3 de 10 usados/)).toBeVisible();
    expect(screen.getByText(/8 usos, sin límite/)).toBeVisible();
  });

  test("indica la oferta aplicada en la lista de productos", () => {
    const product: ManagementProduct = {
      id: 11,
      name: "Cuaderno A5",
      slug: "cuaderno-a5-oferta",
      description: "Cuaderno rayado",
      category: { id: 5, name: "Cuadernos", slug: "cuadernos", parent_id: 2, is_active: true },
      brand: null,
      is_active: true,
      is_sellable: true,
      created_at: "2026-08-20T12:00:00Z",
      on_offer: true,
      active_offer_names: ["Oferta cuadernos"],
      media: [],
      variants: [],
    };

    render(<ManagementProductTable products={[product]} />);

    expect(screen.getByText("En oferta")).toBeVisible();
    expect(screen.getByText("Oferta cuadernos")).toBeVisible();
  });
});
