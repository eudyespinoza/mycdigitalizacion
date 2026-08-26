import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { AnalyticsTracker } from "@/components/analytics/analytics-tracker";
import { ProductViewTracker } from "@/components/analytics/product-view-tracker";
import { apiRequest } from "@/lib/api";
import { flushAnalytics, trackAnalytics } from "@/lib/analytics/client";

let pathname = "/catalogo";
let search = "utm_source=instagram&utm_medium=social";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(search),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiRequest: vi.fn() };
});

beforeEach(() => {
  pathname = "/catalogo";
  search = "utm_source=instagram&utm_medium=social";
  vi.mocked(apiRequest).mockResolvedValue({ accepted: 1 });
});

afterEach(() => {
  vi.clearAllMocks();
});

test("registra una vista por cada navegación normalizada del App Router", async () => {
  const view = render(<AnalyticsTracker />);
  await act(async () => flushAnalytics());
  expect(apiRequest).toHaveBeenCalledTimes(1);

  pathname = "/producto/cuaderno";
  search = "";
  view.rerender(<AnalyticsTracker />);
  await act(async () => flushAnalytics());

  await waitFor(() => expect(apiRequest).toHaveBeenCalledTimes(2));
  expect(vi.mocked(apiRequest).mock.calls[0][1]).toMatchObject({ method: "POST" });
});

test("una falla de analítica nunca rechaza la acción que la originó", async () => {
  vi.mocked(apiRequest).mockRejectedValue(new Error("offline"));

  await expect(
    trackAnalytics({ event_type: "page_view", path: "/catalogo" }),
  ).resolves.toBeUndefined();
  await expect(flushAnalytics()).resolves.toBeUndefined();
});

test("la ficha registra el producto una sola vez", async () => {
  const view = render(<ProductViewTracker productId={17} path="/producto/cuaderno" />);
  view.rerender(<ProductViewTracker productId={17} path="/producto/cuaderno" />);
  await act(async () => flushAnalytics());

  expect(apiRequest).toHaveBeenCalledTimes(1);
  const body = JSON.parse(String(vi.mocked(apiRequest).mock.calls[0][1]?.body));
  expect(body.events[0]).toMatchObject({
    event_type: "product_view",
    product_id: 17,
    path: "/producto/cuaderno",
  });
});
