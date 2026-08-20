import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ProfileForm } from "@/components/account/profile-form";
import { pollPaymentStatus } from "@/components/orders/order-result";
import {
  ApiError,
  apiRequest,
  clearCsrfToken,
  normalizeMediaUrl,
} from "@/lib/api";
import { buildCatalogQuery } from "@/lib/catalog-query";
import { createSerializedQueue } from "@/lib/mutation-queue";
import { checkoutRecoveryFor } from "@/lib/checkout-recovery";
import { buildAddressConfirmation } from "@/lib/address-confirmation";
import type { Customer } from "@/lib/types";

const customer: Customer = {
  id: 5,
  email: "cliente@example.com",
  email_verified_at: "2026-08-20T10:00:00Z",
  profile: { first_name: "Ana", last_name: "Pérez", phone: "1155551234" },
  masked_dni: "••••5678",
  masked_cuit: "",
};

describe("Fix Round 1 contracts", () => {
  beforeEach(() => clearCsrfToken());
  afterEach(() => vi.unstubAllGlobals());

  test("login rotation forces the next protected write to fetch a new CSRF token", async () => {
    const seenTokens: string[] = [];
    let csrfReads = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/auth/csrf/")) {
        csrfReads += 1;
        return new Response(JSON.stringify({ csrf_token: `token-${csrfReads}` }), { status: 200 });
      }
      seenTokens.push(new Headers(init?.headers).get("X-CSRFToken") ?? "");
      return new Response(path.endsWith("/auth/login/") ? JSON.stringify(customer) : undefined, {
        status: path.endsWith("/auth/login/") ? 200 : 204,
      });
    }));

    await apiRequest<Customer>("/auth/login/", { method: "POST", body: "{}" });
    await apiRequest<void>("/addresses/", { method: "POST", body: "{}" });

    expect(seenTokens).toEqual(["token-1", "token-2"]);
    expect(csrfReads).toBe(2);
  });

  test("a named CSRF rejection retries once with a fresh token and unrelated 403 never retries", async () => {
    let protectedCalls = 0;
    let csrfReads = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) {
        csrfReads += 1;
        return new Response(JSON.stringify({ csrf_token: `fresh-${csrfReads}` }), { status: 200 });
      }
      protectedCalls += 1;
      if (protectedCalls === 1) return new Response(JSON.stringify({ code: "csrf_failed", detail: "CSRF token rotated." }), { status: 403 });
      return new Response(undefined, { status: 204 });
    }));
    await apiRequest<void>("/billing-profiles/", { method: "POST", body: "{}" });
    expect(protectedCalls).toBe(2);
    expect(csrfReads).toBe(2);

    clearCsrfToken();
    protectedCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) return new Response(JSON.stringify({ csrf_token: "one" }), { status: 200 });
      protectedCalls += 1;
      return new Response(JSON.stringify({ code: "provider_down", detail: "No disponible" }), { status: 403 });
    }));
    await expect(apiRequest<void>("/checkout/", { method: "POST", body: "{}" })).rejects.toBeInstanceOf(ApiError);
    expect(protectedCalls).toBe(1);
  });

  test("profile editing persists all checkout identity fields and shows the masked DNI", async () => {
    const save = vi.fn(async () => customer);
    render(<ProfileForm customer={{ ...customer, masked_dni: "" }} onSave={save} />);
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Apellido"), { target: { value: "Pérez" } });
    fireEvent.change(screen.getByLabelText("Teléfono"), { target: { value: "1155551234" } });
    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30123123" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await screen.findByText("DNI guardado: ••••5678");
    expect(save).toHaveBeenCalledWith({ first_name: "Ana", last_name: "Pérez", phone: "1155551234", dni: "30123123" });
  });

  test("backend media hosts normalize to public same-origin media without allowing arbitrary origins", () => {
    expect(normalizeMediaUrl("http://backend:8000/media/catalog/item.jpg")).toBe("/media/catalog/item.jpg");
    expect(normalizeMediaUrl("https://store.example/media/hero.webp")).toBe("/media/hero.webp");
    expect(normalizeMediaUrl("/campaigns/pulso-comercial-hero.png")).toBe("/campaigns/pulso-comercial-hero.png");
    expect(normalizeMediaUrl("https://untrusted.example/image.jpg")).toBe("");
  });

  test("catalog URL preserves server facets, attributes, ordering and page", () => {
    expect(buildCatalogQuery({
      q: "cuaderno",
      category: "papeleria",
      brands: ["Acme", "Sur"],
      minPrice: 1000,
      maxPrice: 20000,
      inStock: true,
      onOffer: true,
      attributes: { color: ["azul"], tamaño: ["a5", "a4"] },
      sort: "price_asc",
      page: 3,
    })).toBe("attribute_color=azul&attribute_tama%C3%B1o=a5%2Ca4&availability=in_stock&brand=Acme%2CSur&category=papeleria&max_price=20000&min_price=1000&offer=true&ordering=price_asc&page=3&q=cuaderno");
  });

  test("cart mutation queue cannot let an older response overwrite a newer request", async () => {
    const release: Array<() => void> = [];
    const applied: number[] = [];
    const queue = createSerializedQueue();
    const first = queue.enqueue(async () => { await new Promise<void>((resolve) => release.push(resolve)); applied.push(2); });
    const second = queue.enqueue(async () => { applied.push(3); });
    await waitFor(() => expect(release).toHaveLength(1));
    expect(applied).toEqual([]);
    release[0]();
    await Promise.all([first, second]);
    expect(applied).toEqual([2, 3]);
  });

  test("address confirmation preserves chosen coordinates and requires an explicit written or reverse choice", () => {
    expect(buildAddressConfirmation(-34.6037, -58.3816, "written")).toEqual({ latitude: "-34.6037000", longitude: "-58.3816000", address_choice: "written" });
    expect(buildAddressConfirmation(-34.605, -58.39, "reverse")).toEqual({ latitude: "-34.6050000", longitude: "-58.3900000", address_choice: "reverse" });
  });

  test("checkout domain errors route back to the exact recoverable step", () => {
    expect(checkoutRecoveryFor("identity_missing")).toMatchObject({ step: 0, state: "idle" });
    expect(checkoutRecoveryFor("address_unconfirmed")).toMatchObject({ step: 1, state: "idle" });
    expect(checkoutRecoveryFor("shipping_quote_expired")).toMatchObject({ step: 2, state: "idle" });
    expect(checkoutRecoveryFor("identity_pending_review")).toMatchObject({ step: 0, state: "pending_review" });
    expect(checkoutRecoveryFor("provider_down")).toMatchObject({ step: 2, state: "provider_down" });
  });

  test("pending payment polling is bounded and stops immediately at a terminal server state", async () => {
    const statuses = ["pending", "pending", "approved"];
    const result = await pollPaymentStatus(async () => statuses.shift() ?? "pending", { attempts: 5, intervalMs: 0 });
    expect(result).toEqual({ status: "approved", attempts: 3 });

    const bounded = await pollPaymentStatus(async () => "pending", { attempts: 3, intervalMs: 0 });
    expect(bounded).toEqual({ status: "pending", attempts: 3 });
  });
});
