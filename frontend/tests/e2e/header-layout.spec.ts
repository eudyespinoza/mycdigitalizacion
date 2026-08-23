import { expect, test } from "@playwright/test";

test("desktop trust rail aligns its copy with the public content shell", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "1440", "The horizontal alignment contract is specific to the desktop shell.");
  await page.goto("/");

  const positions = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".header-main")!.getBoundingClientRect();
    const benefits = [...document.querySelectorAll<HTMLElement>(".trust-rail span")].map((item) => item.getBoundingClientRect());
    return {
      shellLeft: shell.left,
      shellCenter: shell.left + shell.width / 2,
      shellRight: shell.right,
      firstLeft: benefits[0].left,
      middleCenter: benefits[1].left + benefits[1].width / 2,
      lastRight: benefits[2].right,
    };
  });

  expect(Math.abs(positions.firstLeft - positions.shellLeft)).toBeLessThanOrEqual(1);
  expect(Math.abs(positions.middleCenter - positions.shellCenter)).toBeLessThanOrEqual(1);
  expect(Math.abs(positions.lastRight - positions.shellRight)).toBeLessThanOrEqual(1);
});
