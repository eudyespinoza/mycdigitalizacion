import { expect, test } from "@playwright/test";

type VitalSnapshot = {
  cls: number;
  lcp: number;
};

test("production landing stays within local Web Vitals proxies", async ({ page }) => {
  await page.addInitScript(() => {
    const snapshot: VitalSnapshot = { cls: 0, lcp: 0 };
    Object.defineProperty(window, "__task6Vitals", {
      configurable: false,
      value: snapshot,
      writable: false,
    });

    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const latest = entries.at(-1);
      if (latest) snapshot.lcp = latest.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });

    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { hadRecentInput: boolean; value: number };
        if (!shift.hadRecentInput) snapshot.cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });

  await page.goto("/", { waitUntil: "networkidle" });
  await page
    .getByRole("img", {
      name: "Cuaderno, botella y accesorios de escritorio en azul, blanco y magenta",
    })
    .evaluate((image: HTMLImageElement) => image.decode());
  await page.waitForTimeout(500);

  const input = page.getByRole("searchbox", { name: /buscar productos/i });
  const interactionMs = await input.evaluate(async (element) => {
    const start = performance.now();
    element.focus();
    element.dispatchEvent(new InputEvent("input", { bubbles: true, data: "cuaderno" }));
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    return performance.now() - start;
  });
  const vitals = await page.evaluate<VitalSnapshot>(() =>
    (window as typeof window & { __task6Vitals: VitalSnapshot }).__task6Vitals,
  );

  test.info().annotations.push(
    { type: "metric", description: `LCP proxy ${vitals.lcp.toFixed(1)}ms` },
    { type: "metric", description: `CLS ${vitals.cls.toFixed(4)}` },
    { type: "metric", description: `interaction-to-next-frame proxy ${interactionMs.toFixed(1)}ms` },
  );

  expect(vitals.lcp).toBeGreaterThan(0);
  expect(vitals.lcp).toBeLessThanOrEqual(2_500);
  expect(vitals.cls).toBeLessThanOrEqual(0.1);
  expect(interactionMs).toBeLessThanOrEqual(200);
});
