"use client";

import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import { useEffect, useRef } from "react";

import type { MapConfiguration } from "@/lib/types";

let loaderKey = "";
let loaderPromise: Promise<{
  maps: google.maps.MapsLibrary;
  marker: google.maps.MarkerLibrary;
}> | null = null;

function loadGoogleMaps(configuration: MapConfiguration) {
  const key = configuration.google_maps_browser_key;
  if (!loaderPromise) {
    loaderKey = key;
    setOptions({
      key,
      v: "weekly",
      language: "es",
      region: "AR",
      authReferrerPolicy: "origin",
      ...(configuration.google_maps_map_id ? { mapIds: [configuration.google_maps_map_id] } : {}),
    });
    loaderPromise = Promise.all([importLibrary("maps"), importLibrary("marker")]).then(
      ([maps, marker]) => ({ maps, marker }),
    );
  }
  if (loaderKey !== key) {
    return Promise.reject(new Error("La clave de Google Maps cambió; recargá la página."));
  }
  return loaderPromise;
}

export function GoogleAddressMapInner({
  configuration,
  latitude,
  longitude,
  onMove,
  onUnavailable,
}: {
  configuration: MapConfiguration;
  latitude: number;
  longitude: number;
  onMove: (latitude: number, longitude: number) => void;
  onUnavailable: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
  const onMoveRef = useRef(onMove);
  const onUnavailableRef = useRef(onUnavailable);

  useEffect(() => { onMoveRef.current = onMove; }, [onMove]);
  useEffect(() => { onUnavailableRef.current = onUnavailable; }, [onUnavailable]);

  useEffect(() => {
    let disposed = false;
    let dragListener: google.maps.MapsEventListener | null = null;

    void loadGoogleMaps(configuration)
      .then(({ maps, marker }) => {
        if (disposed || !containerRef.current) return;
        const position = { lat: latitude, lng: longitude };
        const map = new maps.Map(containerRef.current, {
          center: position,
          zoom: 17,
          mapId: configuration.google_maps_map_id || "DEMO_MAP_ID",
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        });
        const pin = new marker.AdvancedMarkerElement({
          map,
          position,
          title: "Mover punto de entrega",
          gmpDraggable: true,
        });
        dragListener = pin.addListener("dragend", () => {
          const next = pin.position;
          if (!next) return;
          const lat = typeof next.lat === "function" ? next.lat() : next.lat;
          const lng = typeof next.lng === "function" ? next.lng() : next.lng;
          onMoveRef.current(lat, lng);
        });
        mapRef.current = map;
        markerRef.current = pin;
      })
      .catch(() => {
        if (!disposed) onUnavailableRef.current();
      });

    return () => {
      disposed = true;
      dragListener?.remove();
      if (markerRef.current) markerRef.current.map = null;
      markerRef.current = null;
      mapRef.current = null;
    };
  }, [configuration]);

  useEffect(() => {
    const position = { lat: latitude, lng: longitude };
    mapRef.current?.setCenter(position);
    if (markerRef.current) markerRef.current.position = position;
  }, [latitude, longitude]);

  return <div ref={containerRef} className="address-map" role="region" aria-label="Mapa para elegir el punto de entrega" />;
}
