import { expect, test, type Page } from "@playwright/test";

const caseId = "11111111-1111-4111-8111-111111111111";
const mockBaseUrl = `http://127.0.0.1:${process.env.MOCK_PORT ?? "4010"}`;

test.beforeEach(async ({ request }) => {
  await request.post(`${mockBaseUrl}/__control`, { data: { reset: true } });
});

async function expectDocumentFitsViewport(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

async function expectMinimumTarget(page: Page, label: string) {
  const size = await page.getByRole("button", { name: label }).boundingBox();
  expect(size?.width ?? 0).toBeGreaterThanOrEqual(44);
  expect(size?.height ?? 0).toBeGreaterThanOrEqual(44);
}

test("public support creation, recovery and thread stay within the viewport", async ({ page }, testInfo) => {
  await page.goto("/consultas");
  await expect(page.getByRole("heading", { name: "Mis consultas" })).toBeVisible();
  await expect(page.getByLabel("Asunto")).toHaveCount(0);
  await expectDocumentFitsViewport(page);

  await page.getByRole("button", { name: "Nueva consulta" }).click();
  await expect(page.getByRole("dialog", { name: "Nueva consulta" })).toBeVisible();
  await expect(page.getByLabel("Asunto")).toBeVisible();
  await expectDocumentFitsViewport(page);
  await page.getByLabel("Asunto").fill(`Consulta E2E ${testInfo.project.name}`);
  await page.getByLabel("Categoría", { exact: true }).selectOption("productos");
  await page.getByLabel("Mensaje").fill("Necesito información sobre un producto.");
  const createResponse = page.waitForResponse((response) => response.url().endsWith("/api/v1/support/cases/") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Enviar consulta" }).click();
  expect((await createResponse).status()).toBe(201);
  await expect(page.getByRole("heading", { name: "Consulta creada" })).toBeVisible();
  await expect(page.getByText("REC-1234", { exact: true })).toBeVisible();
  await expectMinimumTarget(page, "Entendido");
  await page.getByRole("button", { name: "Entendido" }).click();

  await page.getByRole("button", { name: "Recuperar consulta" }).click();
  await expect(page.getByRole("dialog", { name: "Recuperar consulta" })).toBeVisible();
  await page.getByLabel("Número de consulta").fill("CON-2026-000123");
  await page.getByLabel("Código privado").fill("REC-1234");
  await page.getByRole("button", { name: "Recuperar consulta", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Recuperar consulta" })).toHaveCount(0);

  await page.goto(`/consultas/${caseId}`);
  await expect(page.getByRole("heading", { name: "Consulta de prueba" })).toBeVisible();
  await page.getByRole("textbox", { name: "Mensaje" }).fill("Necesito una actualización.");
  await page.getByRole("button", { name: "Enviar mensaje" }).click();
  await expect(page.getByText("Necesito una actualización.")).toBeVisible();
  await expectDocumentFitsViewport(page);
});

test("problem report and management support flow stay usable without reload", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  await page.goto("/reportar-problema");
  await expect(page.getByRole("heading", { name: "Reportar un problema" })).toBeVisible();
  await expect(page.getByLabel("Categoría", { exact: true })).toBeVisible();
  await page.getByLabel("Asunto").fill(`Problema E2E ${testInfo.project.name}`);
  await page.getByLabel("Categoría", { exact: true }).selectOption("sitio");
  await page.getByLabel("Mensaje").fill("La pantalla no responde como esperaba.");
  const reportResponse = page.waitForResponse((response) => response.url().endsWith("/api/v1/support/cases/") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Enviar reporte" }).click();
  expect((await reportResponse).status()).toBe(201);
  await expect(page.getByRole("heading", { name: "Problema reportado" })).toBeVisible();
  await expectDocumentFitsViewport(page);

  await page.goto("/gestion/consultas");
  await expect(page.getByRole("table", { name: "Consultas y problemas" })).toBeVisible();
  await expect(page.locator(".management-table-wrap")).toHaveCSS("overflow-x", "auto");
  await page.getByLabel("Tipo").selectOption("consultation");
  await page.getByLabel("Estado").selectOption("waiting_staff");
  await page.getByLabel("Prioridad").selectOption("normal");
  await page.getByLabel("Asignación").selectOption("90");
  await page.getByLabel("Sólo pendientes").check();
  await page.getByLabel("Sólo sin leer").check();
  await expect.poll(() => {
    const search = new URL(page.url()).searchParams;
    return [search.get("kind"), search.get("status"), search.get("priority"), search.get("assignee"), search.get("pending"), search.get("unread")];
  }).toEqual(["consultation", "waiting_staff", "normal", "90", "1", "1"]);
  await expect(page.getByRole("cell", { name: "En revisión" }).first()).toBeVisible();
  await expectDocumentFitsViewport(page);

  await page.goto(`/gestion/consultas/${caseId}`);
  await expect(page.getByRole("heading", { name: "Consulta de prueba" })).toBeVisible();
  const detailUrl = page.url();
  await page.getByRole("textbox", { name: "Mensaje" }).fill("Respuesta del equipo sin recarga.");
  const sendButton = page.getByRole("button", { name: "Enviar mensaje" });
  await expectMinimumTarget(page, "Enviar mensaje");
  await sendButton.scrollIntoViewIfNeeded();
  await sendButton.click();
  await expect(page.getByText("Respuesta del equipo sin recarga.")).toBeVisible();
  expect(page.url()).toBe(detailUrl);
  await expectDocumentFitsViewport(page);
});

test("support mock exposes claim and private attachment contracts", async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== "360", "The API contract only needs one deterministic execution.");

  const claim = await request.post(`${mockBaseUrl}/api/v1/support/cases/${caseId}/claim`, {
    data: { code: "REC-1234" },
    headers: { "x-csrftoken": "csrf-1" },
  });
  expect(claim.status()).toBe(200);
  expect((await claim.json()).recovery_code).toBeUndefined();

  for (const path of [
    "/api/v1/support/attachments/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa?preview=1",
    "/api/v1/management/support/attachments/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  ]) {
    const attachment = await request.get(`${mockBaseUrl}${path}`);
    expect(attachment.status()).toBe(200);
    expect(attachment.headers()["x-content-type-options"]).toBe("nosniff");
  }
});
