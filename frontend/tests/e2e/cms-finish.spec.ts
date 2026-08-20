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

test("promotion touch snap stays announced without widening the 360px document", async ({ page }) => {
  await page.goto("/");
  const track = page.getByRole("group", { name: "Promociones" });
  await expect(track).toBeVisible();
  const width = page.viewportSize()?.width ?? 999;
  if (width === 360) {
    const layout = await page.evaluate(() => {
      const controls = document.querySelector<HTMLElement>(".carousel-control-row");
      const buttons = [...(controls?.querySelectorAll("button") ?? [])].map((button) => button.getBoundingClientRect());
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        controls: controls?.getBoundingClientRect(),
        buttons,
      };
    });
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth);
    expect(layout.controls?.left).toBeGreaterThanOrEqual(0);
    expect(layout.controls?.right).toBeLessThanOrEqual(layout.clientWidth);
    expect(layout.buttons.every((button) => button.left >= 0 && button.right <= layout.clientWidth)).toBe(true);
  }

  await page.getByRole("button", { name: "Promoción siguiente" }).click();
  await expect(page.getByText("Promoción 2 de 2")).toBeVisible();
  await page.getByRole("button", { name: "Promoción anterior" }).click();
  await expect(page.getByText("Promoción 1 de 2")).toBeVisible();
  if (width <= 768) {
    await track.evaluate((element) => {
      element.scrollTo({ left: element.scrollWidth - element.clientWidth, behavior: "instant" });
      element.dispatchEvent(new Event("scroll", { bubbles: true }));
    });
    await expect(page.getByText("Promoción 2 de 2")).toBeVisible();
  }
});

test("popup honors daily persistence, elapsed policy, versioned key, image and dismissibility", async ({ page, request }) => {
  await control(request, { popupEnabled: true, popupFrequency: "daily", popupDismissible: true });
  await page.goto("/");
  const popup = page.getByRole("complementary", { name: "Promoción" });
  await expect(popup).toBeVisible();
  await expect(popup.getByRole("img", { name: "Beneficio vigente en azul" })).toBeVisible();
  await popup.getByRole("button", { name: "Cerrar promoción" }).click();
  await page.reload();
  await page.getByRole("button", { name: "Hero siguiente" }).click();
  await expect(page.getByText("Diapositiva 2 de 2")).toBeVisible();
  await expect(popup).toBeHidden();
  await page.evaluate(() => localStorage.setItem("myc-popup:8:v1", String(Date.now() - 86_400_001)));
  await page.reload();
  await expect(popup).toBeVisible();

  await control(request, { popupEnabled: true, popupFrequency: "always", popupDismissible: false });
  await page.reload();
  await expect(popup).toBeVisible();
  await expect(popup.getByRole("button", { name: "Cerrar promoción" })).toHaveCount(0);
});

for (const frequency of ["once_session", "daily", "weekly"] as const) {
  test(`non-dismissible ${frequency} popup records its impression and stays suppressed on reload`, async ({ page, request }) => {
    await control(request, { popupEnabled: true, popupFrequency: frequency, popupDismissible: false });
    await page.goto("/");
    const popup = page.getByRole("complementary", { name: "Promoción" });
    await expect(popup).toBeVisible();
    await expect.poll(() => page.evaluate((kind) => Number((kind === "once_session" ? sessionStorage : localStorage).getItem("myc-popup:8:v1")), frequency)).toBeGreaterThan(0);
    await page.reload();
    await expect(popup).toBeHidden();
  });
}

test("non-dismissible always popup recurs without a frequency impression", async ({ page, request }) => {
  await control(request, { reset: true, popupEnabled: true, popupFrequency: "always", popupDismissible: false });
  await page.goto("/");
  const popup = page.getByRole("complementary", { name: "Promoción" });
  await expect(popup).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("myc-popup:8:v1"))).toBeNull();
  await page.reload();
  await expect(popup).toBeVisible();
});

test("square and horizontal CMS logos keep one proportional accessible lockup", async ({ page, request }) => {
  for (const logoUrl of ["/media/branding/logo/square.png", "/media/branding/logo/horizontal.png"]) {
    await control(request, { logoUrl });
    await page.goto("/");
    const brand = page.getByRole("link", { name: "mycdigitalizacion, inicio" });
    await expect(brand.locator("img")).toHaveCount(1);
    const dimensions = await brand.locator("img").evaluate((image: HTMLImageElement) => {
      const rect = image.getBoundingClientRect();
      return {
        naturalRatio: image.naturalWidth / image.naturalHeight,
        renderedRatio: rect.width / rect.height,
        objectFit: getComputedStyle(image).objectFit,
      };
    });
    expect(dimensions.objectFit).toBe("contain");
    expect(Math.abs(dimensions.renderedRatio - dimensions.naturalRatio)).toBeLessThan(0.02);
  }
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
