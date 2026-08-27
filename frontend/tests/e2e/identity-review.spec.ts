import { expect, test, type APIRequestContext } from "@playwright/test";

const reset = (request: APIRequestContext) =>
  request.post("http://127.0.0.1:4010/__control", { data: { reset: true } });

test.beforeEach(async ({ request }) => {
  await reset(request);
});

test("completed customer data stays reviewable before delivery", async ({ page }, testInfo) => {
  test.skip(
    !["360", "1440"].includes(testInfo.project.name),
    "The identity review is verified once per phone and desktop layout.",
  );

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Revisar mis datos" }).click();

  await expect(page.getByRole("heading", { name: "Tus datos" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Datos completos" })).toBeVisible();
  await expect(page.getByText("DNI ••••5678")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continuar a entrega" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

  await page.screenshot({
    path: `../.impeccable/review/identity-review-${testInfo.project.name}.png`,
    fullPage: true,
  });

  await page.getByRole("button", { name: "Continuar a entrega" }).click();
  await expect(page.getByRole("heading", { name: "Elegí cómo recibir" })).toBeVisible();
});
