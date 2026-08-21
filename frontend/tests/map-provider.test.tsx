import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { IntegrationEditor } from "@/components/management/integration-editor";
import * as AddressMapModule from "@/components/account/address-map";
import type { IntegrationConfiguration } from "@/lib/management/types";


const geolocation: IntegrationConfiguration = {
  provider: "geolocation",
  label: "Mapas",
  enabled: true,
  environment: "production",
  status: "configured",
  public_config: { provider: "openstreetmap", google_maps_map_id: "" },
  secret_fields: { google_maps_browser_key: false },
  version: 1,
  updated_at: null,
  updated_by: "",
  last_test_status: "",
  last_tested_at: null,
  last_test_message: "",
};


describe("proveedor configurable de mapas", () => {
  test("el mapa resuelve OSM por defecto y Google sólo con una clave válida", () => {
    expect(AddressMapModule).toHaveProperty("resolveMapProvider");
    const resolveMapProvider = (
      AddressMapModule as typeof AddressMapModule & {
        resolveMapProvider?: (configuration?: {
          provider: string;
          google_maps_browser_key: string;
          google_maps_map_id: string;
        }) => string;
      }
    ).resolveMapProvider;
    if (!resolveMapProvider) return;

    expect(resolveMapProvider()).toBe("openstreetmap");
    expect(resolveMapProvider({
      provider: "google_maps",
      google_maps_browser_key: "",
      google_maps_map_id: "",
    })).toBe("openstreetmap");
    expect(resolveMapProvider({
      provider: "google_maps",
      google_maps_browser_key: "restricted-browser-key",
      google_maps_map_id: "MYC_MAP_ID",
    })).toBe("google_maps");
  });

  test("Administración ofrece OSM o Google y guarda la clave como credencial", async () => {
    const onSave = vi.fn().mockResolvedValue(geolocation);
    render(<IntegrationEditor integration={geolocation} onSave={onSave} />);

    expect(screen.getByRole("option", { name: "OpenStreetMap (recomendado)" })).toBeVisible();
    expect(screen.getByRole("option", { name: "Google Maps" })).toBeVisible();
    expect(screen.getByLabelText("Clave de navegador de Google Maps")).toHaveValue("");
    expect(screen.getByText(/restringila por dominio/i)).toBeVisible();

    fireEvent.change(screen.getByLabelText("Proveedor del mapa"), {
      target: { value: "google_maps" },
    });
    fireEvent.change(screen.getByLabelText("Clave de navegador de Google Maps"), {
      target: { value: "new-browser-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          public_config: expect.objectContaining({ provider: "google_maps" }),
          secrets: { google_maps_browser_key: "new-browser-key" },
        }),
      ),
    );
  });
});
