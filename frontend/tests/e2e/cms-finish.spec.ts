import { expect, test, type APIRequestContext } from "@playwright/test";

async function control(request: APIRequestContext, body: Record<string, unknown>) {
  await request.post("http://127.0.0.1:4010/__control", { data: body });
}

test.beforeEach(async ({ request }) => { await control(request, { reset: true }); });

test("authored carousels, reduced motion and CMS branding remain operable", async ({ page, request }) => {
  await control(request, { fastCampaigns: true, logoUrl: "/media/branding/logo/active.png", faviconUrl: "/media/branding/favicon/active.png" });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "mycdigitalizacion, inicio" }).locator("img").first()).toHaveAttribute("src", /active\.png/);
  await expect(page.locator('link[rel~="icon"]')).toHaveAttribute("href", /media\/branding\/favicon\/active\.png/);
  await page.getByRole("region", { name: "Promociones vigentes" }).hover();
  await expect(page.getByText("Diapositiva 1 de 2")).toBeVisible();
  await page.waitForTimeout(1_100);
  await expect(page.getByText("Diapositiva 2 de 2")).toBeVisible();
  await page.waitForTimeout(1_200);
  await expect(page.getByText("Diapositiva 2 de 2")).toBeVisible();
  await page.getByRole("button", { name: "Hero anterior" }).click();
  await expect(page.getByRole("heading", { name: "Todo lo que buscás, en un solo lugar" })).toBeVisible();
  await page.getByRole("button", { name: "Promoción siguiente" }).click();
  await expect(page.getByText("Promoción 2 de 2")).toBeVisible();

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await page.waitForTimeout(1_200);
  await expect(page.getByText("Diapositiva 1 de 2")).toBeVisible();
  await page.getByRole("button", { name: "Hero siguiente" }).click();
  await expect(page.getByText("Diapositiva 2 de 2")).toBeVisible();
});

test("popup honors daily persistence, elapsed policy, versioned key, image and dismissibility", async ({ page, request }) => {
  await control(request, { popupEnabled: true, popupFrequency: "daily", popupDismissible: true });
  await page.goto("/");
  const popup = page.getByRole("complementary", { name: "Promoción" });
  await expect(popup).toBeVisible();
  await expect(popup.getByRole("img", { name: "Beneficio vigente en azul" })).toBeVisible();
  await popup.getByRole("button", { name: "Cerrar promoción" }).click();
  await page.reload();
  await expect(popup).toBeHidden();
  await page.evaluate(() => localStorage.setItem("myc-popup:8:v1", String(Date.now() - 86_400_001)));
  await page.reload();
  await expect(popup).toBeVisible();

  await control(request, { popupEnabled: true, popupFrequency: "always", popupDismissible: false });
  await page.reload();
  await expect(popup).toBeVisible();
  await expect(popup.getByRole("button", { name: "Cerrar promoción" })).toHaveCount(0);
});

test("mobile discovery hierarchy and filter chips preserve touch targets", async ({ page }) => {
  await page.goto("/");
  const heading = page.locator(".featured .section-heading");
  if ((page.viewportSize()?.width ?? 999) <= 420) {
    const titleBox = await heading.getByRole("heading").boundingBox();
    const linkBox = await heading.getByRole("link").boundingBox();
    expect(linkBox?.y).toBeGreaterThan((titleBox?.y ?? 0) + (titleBox?.height ?? 0) - 1);
  }
  await page.goto("/catalogo?brand=sur");
  const chip = page.locator(".filter-chips button").first();
  await expect(chip).toBeVisible();
  expect((await chip.boundingBox())?.height).toBeGreaterThanOrEqual(44);
});
