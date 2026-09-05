import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { InventoryTable } from "@/components/management/inventory-table";
import { ManagementProductEditor } from "@/components/management/product-editor";
import { ProductMediaManager } from "@/components/management/product-media-manager";
import { ManagementProductTable } from "@/components/management/product-table";
import { ApiError, apiRequest } from "@/lib/api";
import type { ManagementProduct, ProductEditorPayload } from "@/lib/management/catalog-types";


const product: ManagementProduct = {
  id: 11,
  sku: "600001",
  name: "Cuaderno A5",
  slug: "cuaderno-a5",
  description: "Cuaderno rayado",
  category: { id: 1, name: "Cuadernos", slug: "cuadernos", parent_id: null, is_active: true },
  brand: { id: 2, name: "myc", slug: "myc" },
  is_active: true,
  is_sellable: true,
  created_at: "2026-08-20T12:00:00Z",
  on_offer: false,
  active_offer_names: [],
  media: [],
  variants: [{
    id: 21,
    sku: "600001-01",
    name: "Azul",
    price: "4890.00",
    cost: "2600.00",
    on_hand: 12,
    available_stock: 10,
    stock_is_infinite: false,
    max_purchase_quantity: null,
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
    expect(screen.getByText("600001")).toBeVisible();
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
    fireEvent.change(screen.getByLabelText("Precio"), { target: { value: "4890" } });
    fireEvent.change(screen.getByLabelText("Costo"), { target: { value: "2600" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Cuaderno A5",
        variants: [expect.objectContaining({ cost: "2600" })],
      }),
    ));
    expect(onSave.mock.calls[0][0].variants[0]).not.toHaveProperty("sku");
  });

  test("configura stock infinito y un máximo opcional por carrito", async () => {
    const onSave = vi.fn().mockResolvedValue(product);
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByLabelText("Stock infinito"));
    fireEvent.change(screen.getByLabelText("Cantidad máxima por compra"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        variants: [expect.objectContaining({
          stock_is_infinite: true,
          max_purchase_quantity: 12,
        })],
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

  test("muestra los SKU existentes como datos de solo lectura", () => {
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("SKU del producto")).toHaveTextContent("600001");
    expect(screen.getByLabelText("SKU de variante 1")).toHaveTextContent("600001-01");
    expect(screen.queryByRole("textbox", { name: /SKU/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generar SKU/i })).not.toBeInTheDocument();
  });

  test("anticipa que los SKU nuevos se asignan al guardar", () => {
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Se asignará al guardar")).toHaveLength(2);
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
    fireEvent.change(screen.getByLabelText("Precio"), { target: { value: "4890" } });
    fireEvent.change(screen.getByLabelText("Costo"), { target: { value: "2600" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar variante" }));
    fireEvent.change(screen.getByLabelText("Precio de variante 2"), { target: { value: "4990" } });
    fireEvent.change(screen.getByLabelText("Costo de variante 2"), { target: { value: "2700" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        variants: [
          expect.objectContaining({ cost: "2600" }),
          expect.objectContaining({ cost: "2700" }),
        ],
      }),
    ));
    const savedPayload = onSave.mock.calls[0][0] as ProductEditorPayload;
    expect(savedPayload.variants.every((variant) => !("sku" in variant))).toBe(true);
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

  test("muestra el error de una variante junto al campo exacto y conserva el borrador", async () => {
    const onSave = vi.fn().mockRejectedValue(new ApiError(
      400,
      "validation_error",
      "Revisá los datos ingresados.",
      { "variants.1.price": ["Ingresá un precio válido."] },
    ));
    render(
      <ManagementProductEditor
        brands={[product.brand!]}
        categories={[product.category]}
        initial={product}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Agregar variante" }));
    fireEvent.change(screen.getByLabelText("Precio de variante 2"), {
      target: { value: "4990" },
    });
    fireEvent.change(screen.getByLabelText("Costo de variante 2"), {
      target: { value: "2700" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));

    expect(await screen.findByText("Variante 2 · Precio: Ingresá un precio válido.")).toBeVisible();
    expect(screen.getByLabelText("Precio de variante 2")).toHaveFocus();
  });

  test("resume las medidas plegadas sin perderlas al guardar", async () => {
    const onSave = vi.fn().mockResolvedValue(product);
    render(<ManagementProductEditor brands={[]} categories={[product.category]} initial={product} onSave={onSave} />);
    const weight = screen.getByLabelText("Peso embalado (gramos)");
    const details = weight.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("330 g · 21 × 15 × 2 cm")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      variants: [expect.objectContaining({ packaged_weight_grams: 330, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00" })],
    })));
  });

  test("abre las medidas cuando falla la validación nativa", () => {
    render(<ManagementProductEditor brands={[]} categories={[product.category]} initial={product} onSave={vi.fn()} />);
    const weight = screen.getByLabelText("Peso embalado (gramos)");
    fireEvent.invalid(weight);
    expect(weight.closest("details")).toHaveAttribute("open");
  });

  test("abre y enfoca las medidas cuando el servidor rechaza un campo plegado", async () => {
    const onSave = vi.fn().mockRejectedValue(new ApiError(400, "validation_error", "Revisá los datos.", {
      "variants.0.length_cm": ["Revisá el largo embalado."],
    }));
    render(<ManagementProductEditor brands={[]} categories={[product.category]} initial={product} onSave={onSave} />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    const length = screen.getByLabelText("Largo (cm)");
    await waitFor(() => expect(length).toHaveFocus());
    expect(length.closest("details")).toHaveAttribute("open");
    expect(length).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Revisá el largo embalado.");
  });

  test("conserva la ubicación de errores anidados devuelta por el servidor", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(
      JSON.stringify({
        variants: [
          {},
          { price: ["Ingresá un precio válido."] },
        ],
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    ));

    await expect(apiRequest("/management/products/5/")).rejects.toMatchObject({
      code: "validation_error",
      fields: {
        "variants.1.price": ["Ingresá un precio válido."],
      },
    });
    fetchMock.mockRestore();
  });

  test("ajusta stock con motivo obligatorio", async () => {
    const onAdjust = vi.fn().mockResolvedValue({ ...product.variants[0], on_hand: 18 });
    render(<InventoryTable onAdjust={onAdjust} variants={product.variants} />);
    fireEvent.click(screen.getByRole("button", { name: "Ajustar stock de 600001-01" }));
    fireEvent.change(screen.getByLabelText("Stock físico resultante"), { target: { value: "18" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "Ingreso de mercadería" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await waitFor(() => expect(onAdjust).toHaveBeenCalledWith(21, 18, "Ingreso de mercadería"));
  });

  test("identifica el stock infinito sin ofrecer un ajuste físico", () => {
    render(<InventoryTable
      onAdjust={vi.fn()}
      variants={[{ ...product.variants[0], stock_is_infinite: true, available_stock: 0 }]}
    />);

    expect(screen.getByText("Ilimitado")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Ajustar stock de 600001-01" })).not.toBeInTheDocument();
  });

  test("resume un producto con stock infinito sin mostrar cero disponibles", () => {
    render(<ManagementProductTable products={[{
      ...product,
      variants: [{ ...product.variants[0], stock_is_infinite: true, available_stock: 0 }],
    }]} />);

    expect(screen.getByText("Stock ilimitado")).toBeVisible();
    expect(screen.queryByText("0 disponibles")).not.toBeInTheDocument();
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
    expect(screen.getByLabelText("Archivos")).not.toBeVisible();
    fireEvent.click(screen.getByText("Agregar imágenes"));
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
    expect(await screen.findByAltText("Cuaderno azul - frente.png")).toHaveAttribute("src", "/media/catalog/frente.png");
    expect(screen.getByAltText("Cuaderno azul - interior.png")).toHaveAttribute("src", "/media/catalog/interior.png");
    screen.getAllByRole("button", { name: "Guardar imagen" }).forEach((button) => expect(button).not.toBeVisible());
    fireEvent.click(screen.getByText("Cuaderno azul - frente.png"));
    fireEvent.click(screen.getAllByRole("button", { name: "Eliminar" })[0]);
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(31));
  });
});
