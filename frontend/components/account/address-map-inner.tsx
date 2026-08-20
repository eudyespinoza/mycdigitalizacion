"use client";

import L, { type DragEndEvent } from "leaflet";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import { useEffect, useMemo } from "react";

export function MapRecenter({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap();
  useEffect(() => { map.setView([latitude, longitude], 17, { animate: false }); }, [latitude, longitude, map]);
  return null;
}

export function AddressMapInner({ latitude, longitude, onMove }: { latitude: number; longitude: number; onMove: (latitude: number, longitude: number) => void }) {
  const icon = useMemo(() => L.divIcon({ className: "myc-map-pin", html: "<span></span>", iconSize: [28, 28], iconAnchor: [14, 14] }), []);
  return <MapContainer center={[latitude, longitude]} zoom={17} className="address-map" scrollWheelZoom={false}><MapRecenter latitude={latitude} longitude={longitude} /><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><Marker position={[latitude, longitude]} draggable icon={icon} title="Mover punto de entrega" eventHandlers={{ dragend: (event: DragEndEvent) => { const point = event.target.getLatLng(); onMove(point.lat, point.lng); } }} /></MapContainer>;
}
