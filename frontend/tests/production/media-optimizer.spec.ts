import { expect, test } from "@playwright/test";

test("production optimizer serves same-origin backend media", async ({ request }) => {
  const response = await request.get("/_next/image?url=%2Fmedia%2Fcms%2Fhero.png&w=640&q=75");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toMatch(/^image\/(?:avif|webp|png|jpeg)/);
  expect((await response.body()).byteLength).toBeGreaterThan(1_000);
});

test("home HTML prioritizes one responsive hero without duplicate hero preloads", async ({ request }) => {
  const response = await request.get("/");
  expect(response.status()).toBe(200);
  const html = await response.text();
  const heroPreloads = (html.match(/<link[^>]+rel="preload"[^>]+as="image"[^>]*>/g) ?? [])
    .filter((tag) => /hero(?:-mobile)?\.png/.test(tag));
  const heroImages = html.match(/<img[^>]+alt="Cuaderno, botella y accesorios de escritorio en azul, blanco y magenta"[^>]*>/g) ?? [];
  expect(heroPreloads).toHaveLength(0);
  expect(heroImages).toHaveLength(1);
  expect(heroImages[0]).toMatch(/fetchPriority="high"/);
  expect(html).toMatch(/<source[^>]+media="\(max-width: 768px\)"[^>]+hero-mobile\.png[^>]*>/);
});
