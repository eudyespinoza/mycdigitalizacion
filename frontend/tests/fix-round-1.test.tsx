import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ProfileForm } from "@/components/account/profile-form";
import { OrderDetail } from "@/components/orders/order-detail";
import { pollPaymentStatus } from "@/components/orders/order-result";
import { getTrustedOrderState } from "@/components/checkout/checkout-flow";
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
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { Customer } from "@/lib/types";

const customer: Customer = {
  id: 5,
  email: "cliente@example.com",
  email_verified_at: "2026-08-20T10:00:00Z",
  is_staff: false,
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
      if (protectedCalls === 1) return new Response(JSON.stringify({ code: "csrf_failed", detail: "La sesión de seguridad venció. Actualizá la página e intentá nuevamente." }), { status: 403 });
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

    clearCsrfToken();
    protectedCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) return new Response(JSON.stringify({ csrf_token: "one" }), { status: 200 });
      protectedCalls += 1;
      return new Response(JSON.stringify({ code: "csrf_failure", detail: "legacy mock fantasy" }), { status: 403 });
    }));
    await expect(apiRequest<void>("/billing-profiles/", { method: "POST", body: "{}" })).rejects.toBeInstanceOf(ApiError);
    expect(protectedCalls).toBe(1);
  });

  test("a management permission rejection is presented as an expired session", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "fresh-token" }), { status: 200 });
      }
      return new Response(JSON.stringify({
        detail: "No tenés permiso para acceder al panel de gestión.",
      }), { status: 403 });
    }));

    await expect(apiRequest<void>("/management/products/5/", {
      method: "PATCH",
      body: "{}",
    })).rejects.toMatchObject({
      code: "authentication_required",
      message: "Tu sesión de administración venció. Ingresá nuevamente para guardar los cambios.",
    });
  });

  test("a localized missing-credentials response never leaks framework copy", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "fresh-token" }), { status: 200 });
      }
      return new Response(JSON.stringify({
        detail: "Las credenciales de autenticación no se proveyeron.",
      }), { status: 403 });
    }));

    await expect(apiRequest<void>("/management/products/5/", {
      method: "PATCH",
      body: "{}",
    })).rejects.toMatchObject({
      code: "authentication_required",
      message: "Ingresá a tu cuenta para continuar.",
    });
  });

  test("profile editing persists all checkout identity fields and shows the masked DNI", async () => {
    const save = vi.fn(async () => customer);
    render(<ProfileForm customer={{ ...customer, masked_dni: "" }} onSave={save} />);
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Apellido"), { target: { value: "Pérez" } });
    fireEvent.change(screen.getByLabelText("Teléfono"), { target: { value: "1155551234" } });
    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30123123" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await waitFor(() => expect(screen.getByLabelText("DNI")).toHaveValue("••••5678"));
    expect(screen.getByLabelText("DNI")).toHaveAttribute("readonly");
    expect(save).toHaveBeenCalledWith({ first_name: "Ana", last_name: "Pérez", phone: "1155551234", dni: "30123123" });
  });

  test("a saved DNI is read-only for the customer and links to problem reporting", () => {
    render(<ProfileForm customer={customer} onSave={vi.fn()} />);

    expect(screen.getByLabelText("DNI")).toHaveValue("••••5678");
    expect(screen.getByLabelText("DNI")).toHaveAttribute("readonly");
    expect(screen.getByRole("link", { name: "Reportar un problema" })).toHaveAttribute(
      "href",
      "/reportar-problema",
    );
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
    expect(checkoutRecoveryFor("email_not_verified")).toMatchObject({ step: 0, state: "idle" });
    expect(checkoutRecoveryFor("identity_rejected")).toMatchObject({ step: 0, state: "rejected" });
    expect(checkoutRecoveryFor("address_required")).toMatchObject({ step: 1, state: "idle" });
    expect(checkoutRecoveryFor("address_review_required")).toMatchObject({ step: 1, state: "idle" });
    expect(checkoutRecoveryFor("shipping_quote_expired")).toMatchObject({ step: 2, state: "idle" });
    expect(checkoutRecoveryFor("shipping_quote_changed")).toMatchObject({ step: 2, state: "idle" });
    expect(checkoutRecoveryFor("billing_profile_invalid")).toMatchObject({ step: 3, state: "idle" });
    expect(checkoutRecoveryFor("pickup_unavailable")).toMatchObject({ step: 1, state: "idle" });
    expect(checkoutRecoveryFor("invalid_fulfillment")).toMatchObject({ step: 1, state: "idle" });
    expect(checkoutRecoveryFor("identity_consent_required")).toMatchObject({ step: 0, state: "idle" });
    expect(checkoutRecoveryFor("invalid_email")).toMatchObject({ step: 0, state: "idle" });
    expect(checkoutRecoveryFor("cart_owner_mismatch")).toMatchObject({ step: 0, state: "idle" });
    expect(checkoutRecoveryFor("insufficient_stock")).toMatchObject({ step: 3, state: "idle" });
    expect(checkoutRecoveryFor("purchase_limit_exceeded")).toMatchObject({
      step: 3,
      state: "idle",
      message: expect.stringMatching(/cantidad/i),
    });
    expect(checkoutRecoveryFor("checkout_changed")).toMatchObject({ step: 3, state: "idle" });
    for (const code of ["not_configured", "unavailable", "timeout"]) {
      expect(checkoutRecoveryFor(code, 2)).toMatchObject({ step: 2, state: "provider_down" });
      expect(checkoutRecoveryFor(code, 3)).toMatchObject({ step: 3, state: "provider_down" });
    }
    expect(checkoutRecoveryFor("rejected", 3)).toMatchObject({ step: 3, state: "rejected" });
    expect(checkoutRecoveryFor("invalid_response", 2)).toMatchObject({ step: 2, state: "needs_attention" });
    expect(checkoutRecoveryFor("not_supported", 3)).toMatchObject({ step: 3, state: "needs_attention" });
  });

  test("profile validation focuses the first field that is actually invalid", async () => {
    render(<ProfileForm customer={{ ...customer, masked_dni: "" }} onSave={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await waitFor(() => expect(screen.getByLabelText("DNI")).toHaveFocus());
  });

  test("campaign safe heights remain authored at mobile, tablet and desktop breakpoints", () => {
    expect(campaignHeightStyle({ safe_height_mobile: 320, safe_height_tablet: 460, safe_height_desktop: 580 })).toEqual({
      "--campaign-mobile-height": "320px",
      "--campaign-tablet-height": "460px",
      "--campaign-desktop-height": "580px",
    });
  });

  test("failed payments are presented in backend vocabulary and expose the API resume action", async () => {
    const order = {
      public_id: "33333333-3333-4333-8333-333333333333", identity_status: "verified", payment_status: "failed", fulfillment_status: "unfulfilled", fulfillment_method: "shipping",
      customer_snapshot: {}, address_snapshot: { raw_address: "Av. Corrientes 1234" }, fiscal_snapshot: { id: 3, label: "Personal", legal_name: "Ana Pérez", tax_condition: "consumidor_final", is_default: true, masked_cuit: "20-********-3" }, coupon_code_snapshot: "",
      subtotal_snapshot: "12500.00", discount_snapshot: "0.00", shipping_amount_snapshot: "4500.00", total_snapshot: "17000.00", items: [], timeline: [], shipment: null, pickup_information: null, created_at: "2026-08-20T10:00:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(order), { status: 200 })));
    render(<OrderDetail orderId={order.public_id} />);
    expect(await screen.findByRole("heading", { name: "Pago no completado" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Retomar pago" })).toBeVisible();
  });

  test("customers can see that an administrator cancelled a refunded order", async () => {
    const order = {
      public_id: "44444444-4444-4444-8444-444444444444", identity_status: "verified", payment_status: "refunded", fulfillment_status: "cancelled", fulfillment_method: "shipping",
      customer_snapshot: {}, address_snapshot: { raw_address: "Av. Corrientes 1234" }, fiscal_snapshot: { id: 3, label: "Personal", legal_name: "Ana Pérez", tax_condition: "consumidor_final", is_default: true, masked_cuit: "20-********-3" }, coupon_code_snapshot: "",
      subtotal_snapshot: "12500.00", discount_snapshot: "0.00", shipping_amount_snapshot: "4500.00", total_snapshot: "17000.00", items: [], timeline: [], shipment: null, pickup_information: null, created_at: "2026-08-20T10:00:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(order), { status: 200 })));

    render(<OrderDetail orderId={order.public_id} />);

    expect(await screen.findByText("Entrega: Cancelado.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retomar pago" })).not.toBeInTheDocument();
  });

  test("pending payment polling is bounded and stops immediately at a terminal server state", async () => {
    const statuses = ["not_started", "pending", "paid"];
    const result = await pollPaymentStatus(async () => statuses.shift() ?? "pending", { attempts: 5, intervalMs: 0 });
    expect(result).toEqual({ status: "paid", attempts: 3 });

    const bounded = await pollPaymentStatus(async () => "pending", { attempts: 3, intervalMs: 0 });
    expect(bounded).toEqual({ status: "pending", attempts: 3 });
    expect(getTrustedOrderState(new URLSearchParams("status=approved"), "failed")).toBe("rejected");
    expect(getTrustedOrderState(new URLSearchParams("status=approved"), "refunded")).toBe("refunded");
  });
});
