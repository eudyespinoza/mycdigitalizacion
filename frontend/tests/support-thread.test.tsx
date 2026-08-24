import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { SupportThread } from "@/components/support/support-thread";

const { supportApi, createSupportIdempotencyKey } = vi.hoisted(() => ({
  supportApi: {
    getCase: vi.fn(),
    sendMessage: vi.fn(),
    attachmentDownloadUrl: vi.fn((id: string, preview = false) => `/api/v1/support/attachments/${id}/${preview ? "?preview=1" : ""}`),
  },
  createSupportIdempotencyKey: vi.fn(() => "stable-message-key"),
}));

vi.mock("@/lib/support/api", () => ({ supportApi, createSupportIdempotencyKey }));

const supportCase = {
  public_id: "case-1",
  case_number: "CON-2026-000123",
  kind: "consultation" as const,
  subject: "Consulta por cuadernos",
  category: "productos",
  status: "waiting_customer" as const,
  created_at: "2026-08-23T10:00:00Z",
  updated_at: "2026-08-23T10:00:00Z",
  messages: [{
    id: 8,
    author_role: "staff" as const,
    body: "Te ayudamos con tu compra.",
    created_at: "2026-08-23T10:05:00Z",
    attachments: [{
      public_id: "attachment-1",
      original_name: "respuesta.png",
      detected_mime_type: "image/png",
      size_bytes: 1024,
      image_width: 200,
      image_height: 100,
      preview_url: "/private/should-not-be-used.png",
    }],
  }, {
    id: 4,
    author_role: "guest" as const,
    body: "Mensaje inicial de la consulta.",
    created_at: "2026-08-23T10:01:00Z",
    attachments: [],
  }],
};

describe("hilo de consultas", () => {
  beforeEach(() => {
    vi.useRealTimers();
    supportApi.getCase.mockReset().mockResolvedValue(supportCase);
    supportApi.sendMessage.mockReset().mockResolvedValue({ id: 9 });
    supportApi.attachmentDownloadUrl.mockClear();
    createSupportIdempotencyKey.mockReset().mockReturnValue("stable-message-key");
  });

  afterEach(() => vi.useRealTimers());

  test("muestra el detalle autorizado en orden cronológico y con adjuntos privados", async () => {
    render(<SupportThread publicId="case-1" />);

    expect(await screen.findByRole("heading", { name: "Consulta por cuadernos" })).toBeVisible();
    expect(screen.getByText("Te ayudamos con tu compra.")).toBeVisible();
    expect(screen.getByText("Equipo de atención")).toBeVisible();
    const firstMessage = screen.getByText("Mensaje inicial de la consulta.");
    const secondMessage = screen.getByText("Te ayudamos con tu compra.");
    expect(firstMessage.compareDocumentPosition(secondMessage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const attachment = screen.getByRole("link", { name: /Descargar respuesta\.png/i });
    expect(attachment).toHaveAttribute("href", "/api/v1/support/attachments/attachment-1/");
    expect(screen.getByRole("img", { name: "Vista previa de respuesta.png" })).toHaveAttribute("src", "/api/v1/support/attachments/attachment-1/?preview=1");
    expect(screen.queryByText("/private/should-not-be-used.png")).not.toBeInTheDocument();
  });

  test("envía una respuesta, limpia el compositor sólo al confirmar y vuelve a cargar el hilo", async () => {
    render(<SupportThread publicId="case-1" />);
    const message = await screen.findByLabelText("Mensaje");
    fireEvent.change(message, { target: { value: "Gracias por la ayuda" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    await waitFor(() => expect(supportApi.sendMessage).toHaveBeenCalledWith("case-1", "Gracias por la ayuda", [], "stable-message-key"));
    await waitFor(() => expect(supportApi.getCase).toHaveBeenCalledTimes(2));
    expect(message).toHaveValue("");
  });

  test("reintenta con la misma clave y conserva texto y archivos tras un error", async () => {
    createSupportIdempotencyKey.mockReset().mockReturnValueOnce("retry-key").mockReturnValueOnce("next-key");
    supportApi.sendMessage.mockRejectedValueOnce(new Error("No pudimos enviar el mensaje."));
    render(<SupportThread publicId="case-1" />);
    const message = await screen.findByLabelText("Mensaje");
    const attachment = new File(["png"], "captura.png", { type: "image/png" });
    const attachmentInput = screen.getByLabelText("Adjuntar archivos") as HTMLInputElement;
    Object.defineProperty(attachmentInput, "files", { configurable: true, value: [attachment] });
    fireEvent.change(attachmentInput);
    fireEvent.change(message, { target: { value: "Necesito una respuesta" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos enviar el mensaje.");
    expect(message).toHaveValue("Necesito una respuesta");
    expect(screen.getByText("captura.png")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(supportApi.sendMessage).toHaveBeenCalledTimes(2));
    expect(supportApi.sendMessage).toHaveBeenNthCalledWith(1, "case-1", "Necesito una respuesta", [attachment], "retry-key");
    expect(supportApi.sendMessage).toHaveBeenNthCalledWith(2, "case-1", "Necesito una respuesta", [attachment], "retry-key");
    await waitFor(() => expect(message).toHaveValue(""));
    expect(screen.queryByText("captura.png")).not.toBeInTheDocument();

    fireEvent.change(message, { target: { value: "Nuevo mensaje" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    await waitFor(() => expect(supportApi.sendMessage).toHaveBeenCalledTimes(3));
    expect(supportApi.sendMessage).toHaveBeenLastCalledWith("case-1", "Nuevo mensaje", [], "next-key");
  });

  test("deja el caso cerrado en sólo lectura", async () => {
    supportApi.getCase.mockResolvedValue({ ...supportCase, status: "closed" });
    render(<SupportThread publicId="case-1" />);

    expect(await screen.findByText("Esta consulta está cerrada y no admite nuevas respuestas.")).toBeVisible();
    expect(screen.queryByLabelText("Mensaje")).not.toBeInTheDocument();
  });

  test("cancela el sondeo al desmontarse", async () => {
    vi.useFakeTimers();
    const { unmount } = render(<SupportThread publicId="case-1" pollIntervalMs={10_000} />);
    await act(async () => { await Promise.resolve(); });
    expect(supportApi.getCase).toHaveBeenCalledTimes(1);
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(supportApi.getCase).toHaveBeenCalledTimes(1);
  });
});
