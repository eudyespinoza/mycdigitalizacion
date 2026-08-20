"use client";

import L, { type DragEndEvent } from "leaflet";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import { useMemo } from "react";

export function AddressMapInner({ latitude, longitude, onMove }: { latitude: number; longitude: number; onMove: (latitude: number, longitude: number) => void }) {
  const icon = useMemo(() => L.divIcon({ className: "myc-map-pin", html: "<span></span>", iconSize: [28, 28], iconAnchor: [14, 14] }), []);
  return <MapContainer center={[latitude, longitude]} zoom={17} className="address-map" scrollWheelZoom={false}><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><Marker position={[latitude, longitude]} draggable icon={icon} eventHandlers={{ dragend: (event: DragEndEvent) => { const point = event.target.getLatLng(); onMove(point.lat, point.lng); } }} /></MapContainer>;
}
