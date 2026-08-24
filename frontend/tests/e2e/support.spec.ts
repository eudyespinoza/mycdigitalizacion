import { expect, test, type Page } from "@playwright/test";

const caseId = "11111111-1111-4111-8111-111111111111";

async function expectDocumentFitsViewport(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test("public support creation, recovery and thread stay within the viewport", async ({ page }, testInfo) => {
  test.skip(!["360", "1440"].includes(testInfo.project.name), "The required public overflow checks run at the boundary viewports.");

  await page.goto("/consultas");
  await expect(page.getByRole("heading", { name: "Mis consultas" })).toBeVisible();
  await expect(page.getByLabel("Asunto")).toHaveCount(0);
  await expectDocumentFitsViewport(page);

  await page.getByRole("button", { name: "Nueva consulta" }).click();
  await expect(page.getByRole("dialog", { name: "Nueva consulta" })).toBeVisible();
  await expect(page.getByLabel("Asunto")).toBeVisible();
  await page.getByRole("button", { name: "Cancelar" }).click();

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
  test.skip(!["360", "1440"].includes(testInfo.project.name), "The required management overflow checks run at the boundary viewports.");

  await page.goto("/reportar-problema");
  await expect(page.getByRole("heading", { name: "Reportar un problema" })).toBeVisible();
  await expect(page.getByLabel("Categoría", { exact: true })).toBeVisible();
  await expectDocumentFitsViewport(page);

  await page.goto("/gestion/consultas");
  await expect(page.getByRole("table", { name: "Consultas y problemas" })).toBeVisible();
  await page.getByLabel("Estado").selectOption("waiting_staff");
  await expect(page.getByRole("cell", { name: "En revisión" }).first()).toBeVisible();
  await expectDocumentFitsViewport(page);

  await page.goto(`/gestion/consultas/${caseId}`);
  await expect(page.getByRole("heading", { name: "Consulta de prueba" })).toBeVisible();
  const detailUrl = page.url();
  await page.getByRole("textbox", { name: "Mensaje" }).fill("Respuesta del equipo sin recarga.");
  await page.getByRole("button", { name: "Enviar mensaje" }).click();
  await expect(page.getByText("Respuesta del equipo sin recarga.")).toBeVisible();
  expect(page.url()).toBe(detailUrl);
  await expectDocumentFitsViewport(page);
});
