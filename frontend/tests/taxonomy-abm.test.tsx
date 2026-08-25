import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { TaxonomyPanel } from "@/components/management/taxonomy-panel";

const { managementRequest } = vi.hoisted(() => ({ managementRequest: vi.fn() }));

vi.mock("@/lib/management/api", () => ({ managementRequest }));

const category = { id: 1, name: "Librería", slug: "libreria", parent_id: null, is_active: true };
const brand = { id: 2, name: "myc", slug: "myc" };
const attribute = {
  id: 3,
  name: "Color",
  slug: "color",
  value_type: "option" as const,
  is_filterable: true,
  options: [{ id: 4, label: "Azul", value: "azul" }],
};

describe("ABM de categorías, marcas y atributos", () => {
  beforeEach(() => managementRequest.mockReset());

  test("edita una categoría desde su fila y actualiza la lista", async () => {
    managementRequest.mockResolvedValueOnce({ ...category, name: "Papelería", slug: "papeleria", is_active: false });
    render(<TaxonomyPanel initialAttributes={[attribute]} initialBrands={[brand]} initialCategories={[category]} />);

    fireEvent.click(screen.getByRole("button", { name: "Editar Librería" }));
    const dialog = screen.getByRole("dialog", { name: "Editar categoría" });
    expect(within(dialog).getByLabelText("Nombre de la categoría")).toHaveValue("Librería");
    fireEvent.change(within(dialog).getByLabelText("Nombre de la categoría"), { target: { value: "Papelería" } });
    fireEvent.click(within(dialog).getByLabelText("Habilitada"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith(
      "/categories/1/",
      expect.objectContaining({ method: "PATCH" }),
    ));
    expect(await screen.findByText("Papelería")).toBeVisible();
  });

  test("elimina una marca sólo después de confirmarlo", async () => {
    managementRequest.mockResolvedValueOnce(undefined);
    render(<TaxonomyPanel initialAttributes={[attribute]} initialBrands={[brand]} initialCategories={[category]} />);

    fireEvent.click(screen.getByRole("button", { name: "Eliminar myc" }));
    const dialog = screen.getByRole("dialog", { name: "Eliminar marca" });
    expect(within(dialog).getByText(/myc/)).toBeVisible();
    expect(managementRequest).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Sí, eliminar" }));

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith("/brands/2/", { method: "DELETE" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Editar myc" })).not.toBeInTheDocument());
  });

  test("edita un atributo conservando los identificadores de sus opciones", async () => {
    managementRequest.mockResolvedValueOnce({
      ...attribute,
      name: "Tono",
      slug: "tono",
      options: [{ id: 4, label: "Azul cielo", value: "azul-cielo" }],
    });
    render(<TaxonomyPanel initialAttributes={[attribute]} initialBrands={[brand]} initialCategories={[category]} />);

    fireEvent.click(screen.getByRole("button", { name: "Editar Color" }));
    const dialog = screen.getByRole("dialog", { name: "Editar atributo" });
    fireEvent.change(within(dialog).getByLabelText("Nombre del atributo"), { target: { value: "Tono" } });
    fireEvent.change(within(dialog).getByLabelText("Opciones separadas por coma"), { target: { value: "Azul cielo" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith(
      "/attributes/3/",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining('"id":4'),
      }),
    ));
    expect(await screen.findByText("Tono")).toBeVisible();
  });

  test("ofrece editar y eliminar en los tres submenús", () => {
    render(<TaxonomyPanel initialAttributes={[attribute]} initialBrands={[brand]} initialCategories={[category]} />);

    for (const label of ["Librería", "myc", "Color"]) {
      expect(screen.getByRole("button", { name: `Editar ${label}` })).toBeVisible();
      expect(screen.getByRole("button", { name: `Eliminar ${label}` })).toBeVisible();
    }
  });
});
