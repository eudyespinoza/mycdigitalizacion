import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { SupportHub } from "@/components/support/support-hub";
import { SiteFooter } from "@/components/layout/site-footer";

const { supportApi, createSupportIdempotencyKey } = vi.hoisted(() => ({
  supportApi: {
    configuration: vi.fn(),
    listCases: vi.fn(),
    createCase: vi.fn(),
    recoverCase: vi.fn(),
  },
  createSupportIdempotencyKey: vi.fn(() => "stable-idempotency-key"),
}));

vi.mock("@/lib/support/api", () => ({ supportApi, createSupportIdempotencyKey }));

const configuration = {
  authenticated: false,
  email_available: false,
  categories: {
    consultation: ["productos", "compra", "envios", "pagos", "facturacion", "otra"],
    problem: ["pedido", "pago", "envio", "producto", "cuenta", "sitio", "otro"],
  },
  limits: { max_files: 5, max_file_size_bytes: 10485760, max_total_size_bytes: 31457280 },
};

describe("mesa de ayuda pública", () => {
  beforeEach(() => {
    supportApi.configuration.mockReset().mockResolvedValue(configuration);
    supportApi.listCases.mockReset().mockResolvedValue([]);
    supportApi.createCase.mockReset();
    supportApi.recoverCase.mockReset();
  });

  test("mantiene el alta cerrada hasta solicitar una consulta", async () => {
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");

    expect(screen.queryByRole("dialog", { name: "Nueva consulta" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));

    expect(screen.getByRole("dialog", { name: "Nueva consulta" })).toBeVisible();
    expect(await screen.findByLabelText("Nombre")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Recuperar consulta" })).not.toBeInTheDocument();
  });

  test("enfoca el asunto cuando el formulario termina de prepararse sin robar el foco después", async () => {
    let resolveConfiguration: (value: typeof configuration) => void = () => undefined;
    supportApi.configuration.mockReturnValue(new Promise<typeof configuration>((resolve) => { resolveConfiguration = resolve; }));
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");

    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));
    expect(screen.getByRole("dialog", { name: "Nueva consulta" })).toBeVisible();
    expect(screen.getByText("Preparando el formulario...")).toBeVisible();

    resolveConfiguration(configuration);
    const subject = await screen.findByLabelText("Asunto");
    await waitFor(() => expect(subject).toHaveFocus());

    const category = screen.getByLabelText("Categoría");
    category.focus();
    await Promise.resolve();
    expect(category).toHaveFocus();
  });

  test("reportar un problema abre únicamente el formulario específico", async () => {
    render(<SupportHub initialKind="problem" />);

    expect(screen.getByRole("heading", { name: "Reportar un problema" })).toBeVisible();
    expect(await screen.findByLabelText("Categoría")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Nueva consulta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nueva consulta" })).not.toBeInTheDocument();
  });

  test("abre la recuperación sólo al solicitarla y nunca pide email", async () => {
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");

    fireEvent.click(screen.getByRole("button", { name: "Recuperar consulta" }));

    expect(screen.getByRole("dialog", { name: "Recuperar consulta" })).toBeVisible();
    expect(screen.getByLabelText("Número de consulta")).toBeVisible();
    expect(screen.getByLabelText("Código privado")).toBeVisible();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  test("muestra el código de recuperación una sola vez después de crear", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    supportApi.createCase.mockResolvedValue({
      public_id: "case-1",
      case_number: "CON-2026-000123",
      kind: "consultation",
      subject: "Consulta por cuadernos",
      category: "productos",
      status: "new",
      updated_at: "2026-08-23T10:00:00Z",
      created_at: "2026-08-23T10:00:00Z",
      messages: [],
      recovery_code: "codigo-privado",
    });
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");

    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));
    fireEvent.change(await screen.findByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@example.test" } });
    fireEvent.change(screen.getByLabelText("Asunto"), { target: { value: "Consulta por cuadernos" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "productos" } });
    fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Necesito ayuda con mi compra." } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar consulta" }));

    const confirmation = await screen.findByRole("status");
    expect(within(confirmation).getByText("CON-2026-000123")).toBeVisible();
    expect(within(confirmation).getByText("codigo-privado")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Entendido" }));
    expect(screen.queryByText("codigo-privado")).not.toBeInTheDocument();
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
  });

  test("una cuenta autenticada crea una consulta sin pedir ni enviar datos de contacto", async () => {
    supportApi.configuration.mockResolvedValue({ ...configuration, authenticated: true });
    supportApi.createCase.mockResolvedValue({
      public_id: "case-account-1",
      case_number: "CON-2026-000124",
      kind: "consultation",
      subject: "Consulta desde mi cuenta",
      category: "productos",
      status: "new",
      updated_at: "2026-08-23T10:00:00Z",
      created_at: "2026-08-23T10:00:00Z",
      messages: [],
    });
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");
    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));

    expect(await screen.findByLabelText("Categoría")).toBeVisible();
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Asunto"), { target: { value: "Consulta desde mi cuenta" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "productos" } });
    fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Necesito ayuda con una compra." } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar consulta" }));

    expect(within(await screen.findByRole("status")).getByText("CON-2026-000124")).toBeVisible();
    expect(supportApi.createCase).toHaveBeenCalledWith(expect.objectContaining({
      contact_name: undefined,
      contact_email: undefined,
    }));
  });

  test("una visitante debe completar nombre y email antes de enviar", async () => {
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");
    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));

    expect(await screen.findByLabelText("Nombre")).toBeVisible();
    expect(screen.getByLabelText("Email")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Asunto"), { target: { value: "Consulta de invitada" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "productos" } });
    fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Necesito ayuda con una compra." } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar consulta" }));

    expect(await screen.findByText("Ingresá tu nombre.")).toBeVisible();
    expect(screen.getByText("Ingresá tu email.")).toBeVisible();
    expect(supportApi.createCase).not.toHaveBeenCalled();
  });

  test("rechaza los adjuntos que exceden el límite configurado antes de enviarlos", async () => {
    render(<SupportHub />);
    await screen.findByText("Todavía no tenés consultas abiertas.");
    fireEvent.click(screen.getByRole("button", { name: "Nueva consulta" }));
    fireEvent.change(await screen.findByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@example.test" } });
    fireEvent.change(screen.getByLabelText("Asunto"), { target: { value: "Consulta por cuadernos" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "productos" } });
    fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Necesito ayuda con mi compra." } });
    const attachmentInput = screen.getByLabelText("Adjuntos (opcional)") as HTMLInputElement;
    Object.defineProperty(attachmentInput, "files", {
      configurable: true,
      value: Array.from({ length: 6 }, (_, index) => new File(["nota"], `nota-${index}.txt`, { type: "text/plain" })),
    });
    fireEvent.change(attachmentInput);
    fireEvent.click(screen.getByRole("button", { name: "Enviar consulta" }));

    expect(await screen.findByText("Podés adjuntar hasta 5 archivos.")).toBeVisible();
    expect(supportApi.createCase).not.toHaveBeenCalled();
  });

  test("explica cuando no hay consultas y permite reintentar una carga fallida", async () => {
    supportApi.listCases.mockRejectedValueOnce(new Error("No pudimos cargar tus consultas.")).mockResolvedValueOnce([]);
    render(<SupportHub />);

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar tus consultas.");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Todavía no tenés consultas abiertas.")).toBeVisible();
  });

  test("agrega accesos de soporte al pie", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("link", { name: "Consultas" })).toHaveAttribute("href", "/consultas");
    expect(screen.getByRole("link", { name: "Reportar un problema" })).toHaveAttribute("href", "/reportar-problema");
  });
});
