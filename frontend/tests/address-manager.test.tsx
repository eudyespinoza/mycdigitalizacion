import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { AddressManager } from "@/components/account/address-manager";
import { clearCsrfToken } from "@/lib/api";

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

  test("an unknown postal code keeps locality visible and blocks an incomplete address", async () => {
    render(<AddressManager />);

    fireEvent.change(screen.getByLabelText("CP o CPA"), { target: { value: "3100" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar localidad" }));

    expect(await screen.findByLabelText("Localidad")).toBeVisible();
    expect(screen.getByLabelText("Provincia")).toBeVisible();
    expect(screen.getByRole("button", { name: "Guardar y ubicar" })).toBeDisabled();
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
});
