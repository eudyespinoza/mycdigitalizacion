import { expect, test } from "@playwright/test";

test("production optimizer serves same-origin backend media", async ({ request }) => {
  const response = await request.get("/_next/image?url=%2Fmedia%2Fcms%2Fhero.png&w=640&q=75");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toMatch(/^image\/(?:avif|webp|png|jpeg)/);
  expect((await response.body()).byteLength).toBeGreaterThan(1_000);
});
