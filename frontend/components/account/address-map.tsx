"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import type { MapConfiguration } from "@/lib/types";


const loading = () => <div className="map-loading" role="status">Cargando mapa…</div>;
const OpenStreetMap = dynamic(
  () => import("./address-map-inner").then((module) => module.AddressMapInner),
  { ssr: false, loading },
);
const GoogleMap = dynamic(
  () => import("./google-address-map-inner").then((module) => module.GoogleAddressMapInner),
  { ssr: false, loading },
);

export function resolveMapProvider(configuration?: MapConfiguration) {
  return configuration?.provider === "google_maps" && configuration.google_maps_browser_key
    ? "google_maps"
    : "openstreetmap";
}

export function AddressMap({
  latitude,
  longitude,
  onMove,
  configuration,
}: {
  latitude: number;
  longitude: number;
  onMove: (latitude: number, longitude: number) => void;
  configuration?: MapConfiguration;
}) {
  const provider = resolveMapProvider(configuration);
  const [googleUnavailable, setGoogleUnavailable] = useState(false);
  useEffect(() => setGoogleUnavailable(false), [configuration?.google_maps_browser_key]);
  if (provider === "google_maps" && !googleUnavailable && configuration) {
    return (
      <GoogleMap
        configuration={configuration}
        latitude={latitude}
        longitude={longitude}
        onMove={onMove}
        onUnavailable={() => setGoogleUnavailable(true)}
      />
    );
  }
  return (
    <>
      {googleUnavailable && (
        <p className="map-provider-notice" role="status">
          Google Maps no está disponible. Mostramos OpenStreetMap para que puedas continuar.
        </p>
      )}
      <OpenStreetMap latitude={latitude} longitude={longitude} onMove={onMove} />
    </>
  );
}
