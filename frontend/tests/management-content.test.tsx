import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { ContentEditor } from "@/components/management/content-editor";
import { PromotionEditor } from "@/components/management/promotion-editor";
import { BrandingForm } from "@/components/management/branding-form";


describe("contenido y promociones del panel propio", () => {
  test("edita un hero con alturas, foco, programación e imágenes", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ContentEditor kind="hero" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Vuelta al cole" } });
    fireEvent.change(screen.getByLabelText("Altura escritorio (px)"), { target: { value: "620" } });
    fireEvent.change(screen.getByLabelText("Punto focal horizontal (%)"), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contenido" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      title: "Vuelta al cole",
      safe_height_desktop: 620,
      focal_x: "60",
    })));
    expect(screen.getByLabelText("Imagen para escritorio")).toBeInTheDocument();
    expect(screen.getByLabelText("Imagen para móvil")).toBeInTheDocument();
  });

  test("configura popup con frecuencia, demora y posibilidad de cierre", () => {
    render(<ContentEditor kind="popups" onSave={vi.fn()} />);
    expect(screen.getByLabelText("Frecuencia")).toBeVisible();
    expect(screen.getByLabelText("Demora antes de mostrar (ms)")).toBeVisible();
    expect(screen.getByLabelText("Permitir cerrar")).toBeChecked();
  });

  test("crea promociones automáticas y cupones con vigencia", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<PromotionEditor kind="coupon" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("Código"), { target: { value: "VUELTA20" } });
    fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cupón" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      code: "VUELTA20",
      value: "20",
    })));
  });

  test("permite reemplazar logo y favicon sin agrandar la navegación", () => {
    render(<BrandingForm faviconUrl="/brand/favicon.png" logoUrl="/brand/logo.png" onSave={vi.fn()} />);
    expect(screen.getByAltText("Logo actual")).toHaveAttribute("src", "/brand/logo.png");
    expect(screen.getByLabelText("Nuevo logo")).toBeInTheDocument();
    expect(screen.getByLabelText("Nuevo favicon")).toBeInTheDocument();
  });
});
