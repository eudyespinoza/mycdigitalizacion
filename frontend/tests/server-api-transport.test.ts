import { afterEach, describe, expect, test, vi } from "vitest";

import { serverGet } from "@/lib/api";


describe("server-side API transport", () => {
  afterEach(() => vi.restoreAllMocks());

  test("marks storefront requests as HTTPS behind the internal proxy boundary", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await serverGet<{ ok: boolean }>("/health/");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Forwarded-Proto": "https" }),
      }),
    );
  });
});
