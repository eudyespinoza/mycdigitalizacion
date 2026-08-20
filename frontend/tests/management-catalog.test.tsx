import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { InventoryTable } from "@/components/management/inventory-table";
import { ManagementProductEditor } from "@/components/management/product-editor";
import { ManagementProductTable } from "@/components/management/product-table";
import type { ManagementProduct } from "@/lib/management/catalog-types";


const product: ManagementProduct = {
  id: 11,
  name: "Cuaderno A5",
  slug: "cuaderno-a5",
  description: "Cuaderno rayado",
  category: { id: 1, name: "Cuadernos", slug: "cuadernos", parent_id: null, is_active: true },
  brand: { id: 2, name: "myc", slug: "myc" },
  is_active: true,
  is_sellable: true,
  created_at: "2026-08-20T12:00:00Z",
  variants: [{
    id: 21,
    sku: "CUA-A5",
    name: "Azul",
    price: "4890.00",
    cost: "2600.00",
    on_hand: 12,
    available_stock: 10,
    is_active: true,
    packaged_weight_grams: 330,
    length_cm: "21.00",
    width_cm: "15.00",
    height_cm: "2.00",
  }],
};


describe("gestión de catálogo e inventario", () => {
  test("muestra producto, SKU, precio, costo y stock", () => {
    render(<ManagementProductTable products={[product]} />);
    expect(screen.getByRole("link", { name: "Cuaderno A5" })).toBeVisible();
    expect(screen.getByText("CUA-A5")).toBeVisible();
    expect(screen.getByText("$ 4.890,00")).toBeVisible();
    expect(screen.getByText("$ 2.600,00")).toBeVisible();
    expect(screen.getByText("10 disponibles")).toBeVisible();
  });

  test("crea un producto con una variante completa", async () => {
    const onSave = vi.fn().mockResolvedValue(product);
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        onSave={onSave}
      />,
    );
    fireEvent.change(screen.getByLabelText("Nombre del producto"), { target: { value: "Cuaderno A5" } });
    fireEvent.change(screen.getByLabelText("SKU"), { target: { value: "CUA-A5" } });
    fireEvent.change(screen.getByLabelText("Precio"), { target: { value: "4890" } });
    fireEvent.change(screen.getByLabelText("Costo"), { target: { value: "2600" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Cuaderno A5",
        variants: [expect.objectContaining({ sku: "CUA-A5", cost: "2600" })],
      }),
    ));
  });

  test("ajusta stock con motivo obligatorio", async () => {
    const onAdjust = vi.fn().mockResolvedValue({ ...product.variants[0], on_hand: 18 });
    render(<InventoryTable onAdjust={onAdjust} variants={product.variants} />);
    fireEvent.click(screen.getByRole("button", { name: "Ajustar stock de CUA-A5" }));
    fireEvent.change(screen.getByLabelText("Stock físico resultante"), { target: { value: "18" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "Ingreso de mercadería" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await waitFor(() => expect(onAdjust).toHaveBeenCalledWith(21, 18, "Ingreso de mercadería"));
  });
});
