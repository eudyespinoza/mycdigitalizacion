"use client";

import dynamic from "next/dynamic";
const DynamicMap = dynamic(() => import("./address-map-inner").then((module) => module.AddressMapInner), { ssr: false, loading: () => <div className="map-loading" role="status">Cargando mapa…</div> });
export function AddressMap(props: { latitude: number; longitude: number; onMove: (latitude: number, longitude: number) => void }) { return <DynamicMap {...props} />; }
