import { expect, test } from "@playwright/test";


test("the storefront does not expose framework development controls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open Next.js Dev Tools" })).toHaveCount(0);
});
