import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { InventoryTable } from "@/components/management/inventory-table";
import { ManagementProductEditor } from "@/components/management/product-editor";
import { ProductMediaManager } from "@/components/management/product-media-manager";
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
  media: [],
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
    attributes: [],
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

  test("agrega y guarda varias variantes sin texto de funcionalidad futura", async () => {
    const onSave = vi.fn().mockResolvedValue(product);
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        onSave={onSave}
      />,
    );
    fireEvent.change(screen.getByLabelText("Nombre del producto"), { target: { value: "Cuaderno A5" } });
    fireEvent.change(screen.getByLabelText("SKU"), { target: { value: "CUA-A5-AZUL" } });
    fireEvent.change(screen.getByLabelText("Precio"), { target: { value: "4890" } });
    fireEvent.change(screen.getByLabelText("Costo"), { target: { value: "2600" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar variante" }));
    fireEvent.change(screen.getByLabelText("SKU de variante 2"), { target: { value: "CUA-A5-ROSA" } });
    fireEvent.change(screen.getByLabelText("Precio de variante 2"), { target: { value: "4990" } });
    fireEvent.change(screen.getByLabelText("Costo de variante 2"), { target: { value: "2700" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        variants: [
          expect.objectContaining({ sku: "CUA-A5-AZUL" }),
          expect.objectContaining({ sku: "CUA-A5-ROSA" }),
        ],
      }),
    ));
    expect(screen.queryByText(/después vas a poder/i)).not.toBeInTheDocument();
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

  test("sube y elimina imágenes del producto desde la misma edición", async () => {
    const uploaded = {
      id: 31,
      file_url: "/media/catalog/cuaderno.png",
      responsive_sources: [],
      alt_text: "Cuaderno azul abierto",
      order: 0,
    };
    const onCreate = vi.fn().mockResolvedValue(uploaded);
    const onUpdate = vi.fn().mockResolvedValue(uploaded);
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ProductMediaManager initialMedia={[]} onCreate={onCreate} onDelete={onDelete} onUpdate={onUpdate} />);
    const file = new File(["image"], "cuaderno.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Archivo"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("Texto alternativo"), { target: { value: "Cuaderno azul abierto" } });
    fireEvent.submit(screen.getByRole("button", { name: "Subir imagen" }).closest("form")!);

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.any(FormData)));
    expect(await screen.findByAltText("Cuaderno azul abierto")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(31));
  });
});
