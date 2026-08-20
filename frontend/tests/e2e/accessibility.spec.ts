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
  await page.getByRole("button", { name: /Casa Av\. Corrientes/ }).click();
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
