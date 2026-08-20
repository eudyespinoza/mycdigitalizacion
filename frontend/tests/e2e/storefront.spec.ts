import { expect, test } from "@playwright/test";

test("landing to catalog to product to cart", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /todo lo que buscás/i })).toBeVisible();
  if (testInfo.project.name === "desktop") {
    await page.screenshot({ path: "../.impeccable/review/desktop.png", fullPage: true });
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.screenshot({ path: "../.impeccable/review/hero-repro.png" });
  }
  if (testInfo.project.name === "mobile") await page.screenshot({ path: "../.impeccable/review/mobile.png", fullPage: true });
  await page.getByRole("link", { name: "Explorar catálogo" }).first().click();
  await expect(page.getByRole("heading", { name: "Todo el catálogo" })).toBeVisible();
  await page.getByRole("link", { name: "Ver Cuaderno A5" }).click();
  await expect(page.getByRole("heading", { name: "Cuaderno A5" })).toBeVisible();
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await expect(page.getByRole("dialog", { name: "Tu carrito" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Tu carrito" }).getByText("CUA-A5-AZ", { exact: true })).toBeVisible();
});

test("mocked checkout stops for identity review without claiming payment", async ({ page }) => {
  await page.goto("/checkout");
  await page.getByRole("button", { name: "Validar cuenta" }).click();
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Cotizar envío" }).click();
  await page.getByRole("button", { name: "Ir a Mercado Pago" }).click();
  await expect(page.getByRole("heading", { name: "Validación en revisión" })).toBeVisible();
  await expect(page.getByText(/no reservamos stock/i)).toBeVisible();
  await expect(page.getByText(/pago aprobado/i)).toHaveCount(0);
});
