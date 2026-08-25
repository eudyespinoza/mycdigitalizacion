import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.setTimeout(90_000);

async function expectNoSeriousOrCriticalViolations(page: Page, context: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const violations = results.violations.filter((violation) =>
    violation.impact === "serious" || violation.impact === "critical"
  );
  expect(violations, `${context}\n${JSON.stringify(violations, null, 2)}`).toEqual([]);
}

test("public commerce surfaces have no serious or critical axe violations", async ({ page }) => {
  const routes = ["/", "/catalogo", "/producto/cuaderno-a5", "/cuenta/registro"];
  for (const route of routes) {
    await page.goto(route);
    await expectNoSeriousOrCriticalViolations(page, route);
  }

  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await expect(page.getByRole("dialog", { name: "Tu carrito" })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page, "cart dialog");
});

test("checkout and textual address path have no serious or critical axe violations", async ({ page }) => {
  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await page.keyboard.press("Escape");
  await page.goto("/checkout");
  await expectNoSeriousOrCriticalViolations(page, "checkout account step");

  await page.goto("/cuenta/direcciones");
  await page.getByRole("button", { name: "Agregar dirección" }).click();
  const dialog = page.getByRole("dialog", { name: "Agregar dirección" });
  await dialog.getByLabel("CP o CPA").fill("1043");
  await dialog.getByRole("button", { name: "Buscar localidad" }).click();
  await dialog.getByLabel("Calle").fill("Av. Corrientes");
  await dialog.getByLabel("Número").fill("1234");
  await dialog.getByRole("button", { name: "Guardar y ubicar" }).click();
  await expect(page.getByRole("group", { name: "Alternativa por texto y teclado" })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page, "textual address confirmation");
});

test("keyboard dialogs restore focus and reduced motion removes movement", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/producto/cuaderno-a5");
  const trigger = page.getByRole("button", { name: "Agregar al carrito" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Tu carrito" });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("button", { name: "Cerrar carrito" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();

  const durations = await page.evaluate(() => {
    const button = document.querySelector<HTMLElement>(".button")!;
    const style = getComputedStyle(button);
    return { animation: style.animationDuration, transition: style.transitionDuration };
  });
  expect(durations.animation).toMatch(/^(0s|0\.001s)$/);
  expect(durations.transition).toMatch(/^(0s|0\.001s)$/);

  if (["360", "768"].includes(testInfo.project.name)) {
    await page.goto("/catalogo");
    const filterTrigger = page.getByRole("button", { name: "Filtrar" });
    await filterTrigger.click();
    await expect(page.getByRole("dialog", { name: "Filtros de catálogo" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(filterTrigger).toBeFocused();
  }
});

test("support dialogs, closed thread, and management inbox remain accessible by keyboard", async ({ page }) => {
  await page.goto("/consultas");
  const createTrigger = page.getByRole("button", { name: "Nueva consulta" });
  await createTrigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Nueva consulta" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Asunto")).toBeFocused();
  await expectNoSeriousOrCriticalViolations(page, "support creation dialog");
  await page.keyboard.press("Escape");
  await expect(createTrigger).toBeFocused();

  await page.goto("/consultas/22222222-2222-4222-8222-222222222222");
  await expect(page.getByText("Esta consulta está cerrada y no admite nuevas respuestas.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Mensaje" })).toHaveCount(0);
  await expectNoSeriousOrCriticalViolations(page, "closed support thread");

  await page.goto("/gestion/consultas");
  await expect(page.getByRole("table", { name: "Consultas y problemas" })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page, "management support inbox");
});
