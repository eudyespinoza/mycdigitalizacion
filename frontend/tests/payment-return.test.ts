import { describe, expect, test } from "vitest";

import nextConfig from "@/next.config";

describe("retorno de Mercado Pago", () => {
  test("redirige las preferencias anteriores a la pantalla real de resultado", async () => {
    const redirects = nextConfig.redirects ? await nextConfig.redirects() : [];

    expect(redirects).toContainEqual({
      source: "/checkout/payment-status/:externalReference",
      destination: "/pedido/resultado?external_reference=:externalReference",
      permanent: false,
    });
  });
});
