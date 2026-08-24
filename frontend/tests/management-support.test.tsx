import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import ManagementSupportPage from "@/app/gestion/consultas/page";
import { ManagementSupportCasePanel } from "@/components/management/support-case-panel";
import { ManagementSupportInbox } from "@/components/management/support-inbox";
import { SupportCategoryManager } from "@/components/management/support-category-manager";
import { ManagementNav } from "@/components/management/management-nav";
import { ApiError } from "@/lib/api";

const { managementRequest, managementServerGet, createSupportIdempotencyKey, router } = vi.hoisted(() => ({
  managementRequest: vi.fn(),
  managementServerGet: vi.fn(),
  createSupportIdempotencyKey: vi.fn(() => "support-reply-key"),
  router: { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() },
}));

vi.mock("@/lib/management/api", () => ({ managementRequest }));
vi.mock("@/lib/management/server-api", () => ({
  managementServerGet,
}));
vi.mock("@/lib/support/api", () => ({ createSupportIdempotencyKey }));
vi.mock("next/navigation", () => ({ usePathname: () => "/gestion/consultas", useRouter: () => router }));

const supportCase = {
  public_id: "case-1",
  case_number: "CON-2026-000123",
  kind: "consultation" as const,
  subject: "Consulta por cuadernos",
  category: "productos",
  status: "waiting_staff" as const,
  priority: "high" as const,
  contact_name: "Ana Cliente",
  contact_email: "ana@example.test",
  contact_phone: "+54 11 5555 1234",
  customer: { id: 17, email: "ana@example.test", name: "Ana Cliente" },
  assigned_to: { id: 8, email: "equipo@example.test", name: "Equipo Atención" },
  message_count: 1,
  unread: true,
  created_at: "2026-08-23T10:00:00Z",
  updated_at: "2026-08-23T10:05:00Z",
  order_id: 45,
  product_id: 12,
  source_url: "/productos/cuaderno",
  resolved_at: null,
  closed_at: null,
  staff_last_read_at: null,
  messages: [{
    id: 1,
    author: { id: 17, email: "ana@example.test", name: "Ana Cliente" },
    author_role: "customer" as const,
    body: "Necesito saber el stock.",
    created_at: "2026-08-23T10:00:00Z",
    attachments: [],
  }],
};

const staff = [{
  id: 8,
  email: "equipo@example.test",
  name: "Equipo Atención",
}];

describe("bandeja de soporte de gestión", () => {
  beforeEach(() => {
    vi.useRealTimers();
    managementRequest.mockReset();
    router.push.mockReset();
    router.replace.mockReset();
    router.refresh.mockReset();
    managementServerGet.mockReset().mockImplementation((path: string) => {
      if (path.startsWith("/support/cases")) return Promise.resolve({ count: 1, next: null, previous: null, results: [supportCase] });
      return Promise.resolve({ results: staff });
    });
  });

  afterEach(() => vi.useRealTimers());

  test("muestra una bandeja compacta y no un formulario de alta", async () => {
    render(await ManagementSupportPage({ searchParams: Promise.resolve({ pending: "1" }) }));

    expect(screen.getByRole("table", { name: "Consultas y problemas" })).toBeVisible();
    expect(screen.queryByLabelText("Asunto de nueva consulta")).not.toBeInTheDocument();
    expect(screen.getByText("CON-2026-000123")).toBeVisible();
    expect(managementServerGet).toHaveBeenCalledWith("/support/assignees/");
  });

  test("administra categorías sin mostrar formularios hasta solicitarlos", async () => {
    managementRequest
      .mockResolvedValueOnce({
        id: 3, kind: "consultation", slug: "impresiones-3d", label: "Impresiones 3D",
        sort_order: 30, is_active: true,
      })
      .mockResolvedValueOnce({
        id: 1, kind: "consultation", slug: "productos", label: "Productos y stock",
        sort_order: 10, is_active: true,
      })
      .mockResolvedValueOnce(undefined);
    render(<SupportCategoryManager initialCategories={[
      { id: 1, kind: "consultation", slug: "productos", label: "Productos", sort_order: 10, is_active: true },
      { id: 2, kind: "problem", slug: "pedido", label: "Pedido", sort_order: 10, is_active: true },
    ]} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nueva categoría" }));
    expect(screen.getByRole("dialog", { name: "Nueva categoría" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Tipo de atención"), { target: { value: "consultation" } });
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Impresiones 3D" } });
    fireEvent.change(screen.getByLabelText("Orden"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar categoría" }));
    expect(await screen.findByText("Impresiones 3D")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Editar Productos" }));
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Productos y stock" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(await screen.findByText("Productos y stock")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Eliminar Productos y stock" }));
    expect(screen.getByRole("dialog", { name: "Eliminar categoría" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Sí, eliminar" }));
    await waitFor(() => expect(screen.queryByText("Productos y stock")).not.toBeInTheDocument());
  });

  test("actualiza filtros en la URL y conserva la página cargada", async () => {
    const replaceState = vi.spyOn(window.history, "replaceState");
    managementRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(<ManagementSupportInbox initialData={{ count: 1, next: null, previous: null, results: [supportCase] }} initialFilters={{}} />);

    fireEvent.change(screen.getByLabelText("Estado"), { target: { value: "resolved" } });

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith("/support/cases/?status=resolved"));
    expect(replaceState).toHaveBeenCalledWith(null, "", "/gestion/consultas?status=resolved");
    expect(screen.getByRole("heading", { name: "Consultas" })).toBeVisible();
    replaceState.mockRestore();
  });

  test("espera antes de buscar y nunca navega mediante recarga", async () => {
    vi.useFakeTimers();
    managementRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(<ManagementSupportInbox initialData={{ count: 1, next: null, previous: null, results: [supportCase] }} initialFilters={{}} />);

    fireEvent.change(screen.getByLabelText("Buscar consultas"), { target: { value: "cuaderno" } });
    expect(managementRequest).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });

    expect(managementRequest).toHaveBeenCalledWith("/support/cases/?search=cuaderno");
  });

  test("ofrece una fila enlazada y accesible para abrir el caso", () => {
    render(<ManagementSupportInbox initialData={{ count: 2, next: null, previous: null, results: [supportCase, { ...supportCase, public_id: "case-2", case_number: "CON-2026-000124", subject: "Consulta leída", unread: false }] }} initialFilters={{}} />);

    expect(screen.getByRole("link", { name: /abrir CON-2026-000123/i })).toHaveAttribute("href", "/gestion/consultas/case-1");
    expect(screen.getByRole("cell", { name: "Sin leer" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Leída" })).toBeVisible();
  });

  test("avanza por la paginación ordenada que entrega la API", async () => {
    managementRequest.mockResolvedValue({ count: 2, next: null, previous: "/api/v1/management/support/cases/?page=1", results: [] });
    render(<ManagementSupportInbox initialData={{ count: 2, next: "/api/v1/management/support/cases/?page=2", previous: null, results: [supportCase] }} initialFilters={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Página siguiente" }));

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith("/support/cases/?page=2"));
  });

  test("mantiene la bandeja visible al cargar, fallar o no encontrar resultados", async () => {
    let resolveRequest: (value: unknown) => void = () => undefined;
    managementRequest.mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve; }));
    render(<ManagementSupportInbox initialData={{ count: 1, next: null, previous: null, results: [supportCase] }} initialFilters={{}} />);

    fireEvent.change(screen.getByLabelText("Prioridad"), { target: { value: "urgent" } });
    expect(screen.getByRole("status")).toHaveTextContent("Cargando consultas");
    resolveRequest({ count: 0, next: null, previous: null, results: [] });
    expect(await screen.findByText("No hay consultas con estos filtros.")).toBeVisible();

    managementRequest.mockRejectedValueOnce(new Error("No pudimos cargar las consultas."));
    fireEvent.change(screen.getByLabelText("Prioridad"), { target: { value: "low" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar las consultas.");
    expect(screen.getByRole("heading", { name: "Consultas" })).toBeVisible();
  });

  test("no deja que una respuesta antigua reemplace los filtros más recientes", async () => {
    let resolveOlder: (value: unknown) => void = () => undefined;
    const older = new Promise((resolve) => { resolveOlder = resolve; });
    managementRequest.mockImplementationOnce(() => older).mockResolvedValueOnce({
      count: 1, next: null, previous: null, results: [{ ...supportCase, subject: "Resultado reciente" }],
    });
    render(<ManagementSupportInbox initialData={{ count: 1, next: null, previous: null, results: [supportCase] }} initialFilters={{}} />);

    fireEvent.change(screen.getByLabelText("Estado"), { target: { value: "resolved" } });
    fireEvent.change(screen.getByLabelText("Prioridad"), { target: { value: "low" } });
    expect(await screen.findByText("Resultado reciente")).toBeVisible();
    resolveOlder({ count: 1, next: null, previous: null, results: [{ ...supportCase, subject: "Resultado antiguo" }] });

    await waitFor(() => expect(screen.queryByText("Resultado antiguo")).not.toBeInTheDocument());
    expect(screen.getByText("Resultado reciente")).toBeVisible();
  });

  test("responde y actualiza el hilo sin recargar la página", async () => {
    const pushState = vi.spyOn(window.history, "pushState");
    const replaceState = vi.spyOn(window.history, "replaceState");
    const locationBeforeReply = window.location.href;
    const message = { ...supportCase.messages[0], id: 2, author_role: "staff" as const, body: "Respuesta del equipo" };
    managementRequest.mockResolvedValue(message);
    render(<ManagementSupportCasePanel initialAssignees={staff} initialCase={supportCase} />);
    const attachment = new File(["archivo"], "respuesta.txt", { type: "text/plain" });
    const input = screen.getByLabelText("Adjuntar archivos") as HTMLInputElement;
    Object.defineProperty(input, "files", { configurable: true, value: [attachment] });
    fireEvent.change(input);
    fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Respuesta del equipo" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    await waitFor(() => expect(managementRequest).toHaveBeenCalledWith("/support/cases/case-1/messages/", expect.objectContaining({ method: "POST" })));
    const [, request] = managementRequest.mock.calls[0] as [string, RequestInit];
    const body = request.body as FormData;
    expect(body.get("body")).toBe("Respuesta del equipo");
    expect(body.get("idempotency_key")).toBe("support-reply-key");
    expect(body.getAll("attachments")).toEqual([attachment]);
    expect(await screen.findByText("Respuesta del equipo")).toBeVisible();
    expect(screen.queryByText("respuesta.txt")).not.toBeInTheDocument();
    expect(window.location.href).toBe(locationBeforeReply);
    expect(pushState).not.toHaveBeenCalled();
    expect(replaceState).not.toHaveBeenCalled();
    expect(router.push).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
    expect(router.refresh).not.toHaveBeenCalled();
    pushState.mockRestore();
    replaceState.mockRestore();
  });

  test("reemplaza el caso con la respuesta autoritativa del PATCH y conserva el estado ante error", async () => {
    managementRequest.mockResolvedValueOnce({ ...supportCase, status: "resolved" });
    render(<ManagementSupportCasePanel initialAssignees={staff} initialCase={supportCase} />);

    fireEvent.change(screen.getByLabelText("Estado del caso"), { target: { value: "resolved" } });
    await waitFor(() => expect(screen.getByText("Resuelta")).toBeVisible());
    expect(managementRequest).toHaveBeenCalledWith("/support/cases/case-1/", expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "resolved" }) }));

    managementRequest.mockRejectedValueOnce(new Error("No se pudo guardar."));
    fireEvent.change(screen.getByLabelText("Prioridad del caso"), { target: { value: "low" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo guardar.");
    expect((screen.getByLabelText("Prioridad del caso") as HTMLSelectElement).value).toBe("high");
  });

  test("carga y selecciona los asignables de atención", async () => {
    render(await ManagementSupportPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByRole("option", { name: "Equipo Atención" })).toHaveValue("8");
    expect(managementServerGet).toHaveBeenCalledWith("/support/assignees/");
  });

  test("permite reintentar la carga de asignables sin bloquear otras operaciones", async () => {
    managementServerGet.mockImplementation((path: string) => path.startsWith("/support/cases")
      ? Promise.resolve({ count: 1, next: null, previous: null, results: [supportCase] })
      : Promise.reject(new Error("sin conexión")));
    managementRequest.mockResolvedValue({ results: staff });
    render(await ManagementSupportPage({ searchParams: Promise.resolve({}) }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar las personas disponibles para asignar.");
    expect(screen.getByLabelText("Estado")).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByRole("option", { name: "Equipo Atención" })).toHaveValue("8");
    expect(managementRequest).toHaveBeenCalledWith("/support/assignees/");
  });

  test("deshabilita la asignación si atención sólo puede responder", async () => {
    managementRequest.mockRejectedValueOnce(new ApiError(403, "permission_denied", "No autorizado."));
    render(<ManagementSupportCasePanel initialAssigneeError="No pudimos cargar las personas disponibles para asignar. Reintentá." initialCase={supportCase} />);

    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("No tenés permiso para asignar responsables.")).toBeVisible();
    expect(screen.getByLabelText("Asignar a")).toBeDisabled();
    expect(screen.getByLabelText("Estado del caso")).not.toBeDisabled();
    expect(screen.getByLabelText("Prioridad del caso")).not.toBeDisabled();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  test("muestra un contador de pendientes accesible y tolera que falle el resumen", async () => {
    managementRequest.mockResolvedValueOnce({ pending: 3, unread: 2 });
    const { unmount } = render(<ManagementNav />);
    expect(await screen.findByRole("link", { name: "Consultas, 2 sin leer" })).toHaveAttribute("href", "/gestion/consultas");

    managementRequest.mockRejectedValueOnce(new Error("sin conexión"));
    unmount();
    render(<ManagementNav />);
    expect(await screen.findByRole("link", { name: "Consultas, sin consultas sin leer" })).toBeVisible();
  });
});
