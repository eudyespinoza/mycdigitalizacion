import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { InventoryTable } from "@/components/management/inventory-table";
import { ManagementProductEditor } from "@/components/management/product-editor";
import { ProductMediaManager } from "@/components/management/product-media-manager";
import { ManagementProductTable } from "@/components/management/product-table";
import { ApiError } from "@/lib/api";
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

  test("actualiza el identificador web con el nombre hasta que se edita manualmente", () => {
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Nombre del producto"), {
      target: { value: "Cuaderno cuadriculado" },
    });
    expect(screen.getByLabelText("Identificador para la web")).toHaveValue("cuaderno-cuadriculado");

    fireEvent.change(screen.getByLabelText("Identificador para la web"), {
      target: { value: "cuaderno-escolar-personalizado" },
    });
    fireEvent.change(screen.getByLabelText("Nombre del producto"), {
      target: { value: "Cuaderno escolar" },
    });
    expect(screen.getByLabelText("Identificador para la web")).toHaveValue("cuaderno-escolar-personalizado");
  });

  test("genera un SKU desde la marca, el producto y la variante", () => {
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Nombre del producto"), {
      target: { value: "Cuaderno cuadriculado" },
    });
    fireEvent.change(screen.getByLabelText("Nombre de la variante"), {
      target: { value: "Celeste" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generar SKU" }));

    expect(screen.getByLabelText("SKU")).toHaveValue("MYC-CUA-CUA-CEL");
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

  test("keeps the product draft visible and offers a new-tab login when the session expires", async () => {
    const onSave = vi.fn().mockRejectedValue(new ApiError(
      403,
      "authentication_required",
      "Tu sesión de administración venció. Ingresá nuevamente para guardar los cambios.",
    ));
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText("Nombre del producto"), {
      target: { value: "Cuaderno A5 actualizado" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));

    expect(await screen.findByText("Tu sesión de administración venció. Ingresá nuevamente para guardar los cambios.")).toBeVisible();
    expect(screen.getByLabelText("Nombre del producto")).toHaveValue("Cuaderno A5 actualizado");
    expect(screen.queryByText("No pudimos guardar el producto. Revisá los campos.")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ingresar en otra pestaña" })).toHaveAttribute(
      "href",
      "/cuenta/ingresar?next=%2Fgestion%2Fcatalogo%2F11",
    );
    expect(screen.getByRole("link", { name: "Ingresar en otra pestaña" })).toHaveAttribute("target", "_blank");
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
    const uploaded = (id: number, name: string) => ({
      id,
      file_url: `/media/catalog/${name}`,
      responsive_sources: [],
      alt_text: `Cuaderno azul - ${name}`,
      order: id,
      variant_id: 21,
      variant_name: "Azul",
    });
    const onCreate = vi.fn()
      .mockResolvedValueOnce(uploaded(31, "frente.png"))
      .mockResolvedValueOnce(uploaded(32, "interior.png"));
    const onUpdate = vi.fn().mockResolvedValue(uploaded(31, "frente.png"));
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ProductMediaManager initialMedia={[]} onCreate={onCreate} onDelete={onDelete} onUpdate={onUpdate} variants={product.variants} />);
    const files = [
      new File(["front"], "frente.png", { type: "image/png" }),
      new File(["inside"], "interior.png", { type: "image/png" }),
    ];
    fireEvent.change(screen.getByLabelText("Archivos"), { target: { files } });
    fireEvent.change(screen.getByLabelText("Texto alternativo base"), { target: { value: "Cuaderno azul" } });
    fireEvent.change(screen.getByLabelText("Asignar imágenes a"), { target: { value: "21" } });
    fireEvent.submit(screen.getByRole("button", { name: "Subir imagen" }).closest("form")!);

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(2));
    expect(Array.from(onCreate.mock.calls[0][0] as FormData)).toEqual(expect.arrayContaining([
      ["variant_id", "21"],
    ]));
    expect(await screen.findByAltText("Cuaderno azul - frente.png")).toBeVisible();
    expect(screen.getByAltText("Cuaderno azul - interior.png")).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Eliminar" })[0]);
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(31));
  });
});
