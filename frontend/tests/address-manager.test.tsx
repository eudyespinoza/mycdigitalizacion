import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { AddressManager } from "@/components/account/address-manager";
import { clearCsrfToken } from "@/lib/api";

const savedAddress = {
  id: 12,
  label: "Casa",
  raw_address: "1 de mayo 2168, PARANA, ENTRE RIOS",
  normalized_address: "1 de mayo 2168, Paraná, Entre Ríos",
  street: "1 de mayo",
  number: "2168",
  postal_code: "3100",
  cpa: "",
  locality: "PARANA",
  province: "ENTRE RIOS",
  latitude: "-31.7377825",
  longitude: "-60.5494782",
  floor: "",
  apartment: "",
  reference: "",
  notes: "",
  geocode_source: "openstreetmap",
  geocode_confidence: null,
  geocode_summary: { precision: "address" },
  needs_review: true,
  reviewed_at: null,
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:00Z",
};

describe("AddressManager", () => {
  beforeEach(() => {
    clearCsrfToken();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/locations/postal-lookup/")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/addresses/")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/locations/map-config/")) {
        return new Response(JSON.stringify({
          provider: "openstreetmap",
          google_maps_browser_key: "",
          google_maps_map_id: "",
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
  });

  afterEach(() => vi.unstubAllGlobals());

  test("keeps the new address form hidden until the customer requests it", async () => {
    render(<AddressManager />);

    expect(screen.queryByLabelText("CP o CPA")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Agregar dirección" }));

    const dialog = screen.getByRole("dialog", { name: "Agregar dirección" });
    expect(within(dialog).getByLabelText("CP o CPA")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "Guardar y ubicar" })).toBeDisabled();
  });

  test("an unknown postal code keeps locality visible and blocks an incomplete address", async () => {
    render(<AddressManager />);

    fireEvent.click(screen.getByRole("button", { name: "Agregar dirección" }));
    const dialog = screen.getByRole("dialog", { name: "Agregar dirección" });

    fireEvent.change(within(dialog).getByLabelText("CP o CPA"), { target: { value: "3100" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Buscar localidad" }));

    expect(await within(dialog).findByLabelText("Localidad")).toBeVisible();
    expect(within(dialog).getByLabelText("Provincia")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "Guardar y ubicar" })).toBeDisabled();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "No encontramos localidades para ese código postal",
      );
    });
  });

  test("a locality center cannot be presented as the exact written address", async () => {
    const approximateAddress = {
      id: 12,
      label: "Casa",
      raw_address: "1 de mayo 2168, PARANA, ENTRE RIOS",
      normalized_address: "1 de mayo 2168, Paraná, Entre Ríos",
      street: "1 de mayo",
      number: "2168",
      postal_code: "3100",
      cpa: "",
      locality: "PARANA",
      province: "ENTRE RIOS",
      latitude: "-31.7401602",
      longitude: "-60.5274260",
      floor: "",
      apartment: "",
      reference: "",
      notes: "",
      geocode_source: "georef",
      geocode_confidence: null,
      geocode_summary: { precision: "locality" },
      needs_review: true,
      reviewed_at: null,
      created_at: "2026-08-25T00:00:00Z",
      updated_at: "2026-08-25T00:00:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/addresses/")) {
        return new Response(JSON.stringify([approximateAddress]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/locations/map-config/")) {
        return new Response(JSON.stringify({
          provider: "openstreetmap",
          google_maps_browser_key: "",
          google_maps_map_id: "",
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));

    render(<AddressManager />);
    const addressText = await screen.findByText("1 de mayo 2168, PARANA, ENTRE RIOS");
    const addressRow = addressText.closest("button");
    expect(addressRow).not.toBeNull();
    fireEvent.click(addressRow!);

    expect(screen.getByRole("heading", { name: "No encontramos la altura exacta" })).toBeVisible();
    expect(screen.getByText(/pin marca por ahora el centro de PARANA/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirmar esta dirección" })).not.toBeInTheDocument();
  });

  test("a saved address can be edited and geocoded again", async () => {
    let address = { ...savedAddress };
    const requests: Array<{ url: string; method: string; body: string }> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      requests.push({ url, method, body: String(init?.body ?? "") });
      if (url.endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "address-csrf" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/locations/map-config/")) {
        return new Response(JSON.stringify({ provider: "openstreetmap", google_maps_browser_key: "", google_maps_map_id: "" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/addresses/") && method === "GET") {
        return new Response(JSON.stringify([address]), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/addresses/12/") && method === "PATCH") {
        address = { ...address, street: "Avenida Almafuerte", number: "982", raw_address: "Avenida Almafuerte 982, PARANA, ENTRE RIOS" };
        return new Response(JSON.stringify(address), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/locations/geocode/") && method === "POST") {
        return new Response(JSON.stringify(address), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }));

    render(<AddressManager />);
    fireEvent.click(await screen.findByRole("button", { name: "Editar dirección Casa" }));
    const dialog = screen.getByRole("dialog", { name: "Editar dirección" });
    expect(within(dialog).getByLabelText("Calle")).toHaveValue("1 de mayo");
    fireEvent.change(within(dialog).getByLabelText("Calle"), { target: { value: "Avenida Almafuerte" } });
    fireEvent.change(within(dialog).getByLabelText("Número"), { target: { value: "982" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar dirección" }));

    expect((await screen.findAllByText("Avenida Almafuerte 982, PARANA, ENTRE RIOS"))[0]).toBeVisible();
    expect(requests.some((request) => request.method === "PATCH" && request.url.endsWith("/addresses/12/") && request.body.includes("Avenida Almafuerte"))).toBe(true);
    expect(requests.some((request) => request.method === "POST" && request.url.endsWith("/locations/geocode/") && request.body.includes('"address_id":12'))).toBe(true);
    expect(screen.queryByRole("dialog", { name: "Editar dirección" })).not.toBeInTheDocument();
  });

  test("a saved address can be deleted after an in-app confirmation", async () => {
    let addressPresent = true;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "address-csrf" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/locations/map-config/")) {
        return new Response(JSON.stringify({ provider: "openstreetmap", google_maps_browser_key: "", google_maps_map_id: "" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/addresses/") && method === "GET") {
        return new Response(JSON.stringify(addressPresent ? [savedAddress] : []), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/addresses/12/") && method === "DELETE") {
        addressPresent = false;
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }));

    render(<AddressManager />);
    fireEvent.click(await screen.findByRole("button", { name: "Eliminar dirección Casa" }));
    const confirmation = screen.getByRole("dialog", { name: "¿Eliminar la dirección Casa?" });
    expect(within(confirmation).getByText(/Esta acción no se puede deshacer/)).toBeVisible();
    fireEvent.click(within(confirmation).getByRole("button", { name: "Eliminar dirección" }));

    await waitFor(() => expect(screen.queryByText("1 de mayo 2168, PARANA, ENTRE RIOS")).not.toBeInTheDocument());
    expect(screen.getByText("Todavía no guardaste direcciones.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Agregar dirección" })).toBeEnabled();
  });
});
