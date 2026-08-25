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
});
