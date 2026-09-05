import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("alta y edición de catálogo mantienen campos legibles y ajustes bajo demanda", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  for (const [route, heading, mode] of [
    ["/gestion/catalogo/nuevo", "Nuevo producto", "new"],
    ["/gestion/catalogo/7", "Cuaderno A5", "edit"],
  ]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByLabel("Nombre del producto")).toBeVisible();
    await expect(page.getByLabel("Precio", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Peso embalado (gramos)", { exact: true })).not.toBeVisible();

    const metrics = await page.evaluate(() => {
      const form = document.querySelector<HTMLElement>(".product-editor")!;
      const aside = document.querySelector<HTMLElement>(".product-editor-media")!;
      return {
        fits: document.documentElement.scrollWidth <= innerWidth + 1,
        formFits: form.scrollWidth <= form.clientWidth + 1,
        sideBySide: aside.getBoundingClientRect().left >= form.getBoundingClientRect().right,
        summaryDisplay: getComputedStyle(form.querySelector("summary")!).display,
        fields: Array.from(form.querySelectorAll<HTMLInputElement>("input:not([type=checkbox]), select")).filter((node) => node.checkVisibility()).map((node) => ({ width: node.clientWidth, height: node.getBoundingClientRect().height })),
      };
    });
    expect(metrics.fits).toBe(true);
    expect(metrics.formFits).toBe(true);
    expect(metrics.summaryDisplay).toBe("grid");
    expect(metrics.sideBySide).toBe(testInfo.project.name === "1440");
    metrics.fields.forEach((field) => { expect(field.height).toBeGreaterThanOrEqual(44); expect(field.width).toBeGreaterThanOrEqual(110); });
    await page.screenshot({ path: `../output/catalog-editor-${mode}-${testInfo.project.name}.png`, fullPage: true });

    if (["360", "1440"].includes(testInfo.project.name)) {
      const a11y = await new AxeBuilder({ page }).include(".management-product-page").analyze();
      expect(a11y.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
    }
  }

  await page.getByText("Agregar imágenes", { exact: true }).click();
  await expect(page.getByLabel("Archivos")).toBeVisible();
  await page.getByText("Cuaderno azul, vista frontal", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Guardar imagen", exact: true })).toBeVisible();

  // Native validation must reveal a folded field before trying to focus it.
  const measures = page.locator(".product-variant").first().locator("details");
  await measures.locator("summary").click();
  const weight = page.getByLabel("Peso embalado (gramos)", { exact: true });
  await weight.fill("0");
  await measures.locator("summary").click();
  await page.getByRole("button", { name: "Guardar producto" }).click();
  await expect(weight).toBeVisible();
  await expect(weight).toBeFocused();
});
