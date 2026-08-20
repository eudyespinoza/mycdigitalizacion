"use client";

import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { buildAddressConfirmation } from "@/lib/address-confirmation";
import { requiresReverseLookup } from "@/lib/geo";
import type { Address } from "@/lib/types";
import { AddressMap } from "./address-map";

type Locality = { postal_code: string; cpa: string; locality: string; province: string };
type Point = { latitude: number; longitude: number };
const empty = { label: "Casa", raw_address: "", street: "", number: "", postal_code: "", cpa: "", locality: "", province: "", floor: "", apartment: "", reference: "", notes: "" };

export function AddressManager() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [values, setValues] = useState(empty);
  const [localities, setLocalities] = useState<Locality[]>([]);
  const [current, setCurrent] = useState<Address | null>(null);
  const [origin, setOrigin] = useState<Point | null>(null);
  const [point, setPoint] = useState<Point | null>(null);
  const [latitudeInput, setLatitudeInput] = useState("");
  const [longitudeInput, setLongitudeInput] = useState("");
  const [writtenAddress, setWrittenAddress] = useState("");
  const [reverseAddress, setReverseAddress] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const messageRef = useRef<HTMLParagraphElement>(null);

  const load = () => apiRequest<Address[]>("/addresses/").then(setAddresses).catch((cause) => setError(cause instanceof Error ? cause.message : "No pudimos cargar las direcciones."));
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (message) messageRef.current?.focus(); }, [message]);

  const selectAddress = (address: Address) => {
    const next = address.latitude && address.longitude ? { latitude: Number(address.latitude), longitude: Number(address.longitude) } : null;
    setCurrent(address); setOrigin(next); setPoint(next); setLatitudeInput(next ? String(next.latitude) : ""); setLongitudeInput(next ? String(next.longitude) : ""); setWrittenAddress(address.raw_address); setReverseAddress("");
  };
  const postalLookup = async () => {
    setError("");
    try {
      const rows = await apiRequest<Locality[]>(`/locations/postal-lookup/?postal_code=${encodeURIComponent(values.postal_code)}`);
      setLocalities(rows);
      if (rows[0]) setValues((previous) => ({ ...previous, cpa: rows[0].cpa, locality: rows[0].locality, province: rows[0].province }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No encontramos ese código postal."); }
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const raw_address = `${values.street} ${values.number}, ${values.locality}, ${values.province}`;
      const address = await apiRequest<Address>("/addresses/", { method: "POST", body: JSON.stringify({ ...values, raw_address }) });
      const geocoded = await apiRequest<Address>("/locations/geocode/", { method: "POST", body: JSON.stringify({ address_id: address.id }) });
      selectAddress(geocoded); setMessage("Dirección guardada. Confirmá el punto sugerido antes de usarla."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos guardar o ubicar la dirección."); }
    finally { setBusy(false); }
  };
  const reverse = async () => {
    if (!current || !point) return;
    setBusy(true); setError("");
    try {
      const result = await apiRequest<{ address: Address; location: { formatted_address?: string; normalized_address?: string } }>("/locations/reverse-geocode/", { method: "POST", body: JSON.stringify({ address_id: current.id, latitude: point.latitude.toFixed(7), longitude: point.longitude.toFixed(7) }) });
      setCurrent(result.address);
      setReverseAddress(result.location.formatted_address || result.location.normalized_address || result.address.normalized_address || result.address.raw_address);
      setMessage("Encontramos una dirección para el punto. Elegí cuál querés conservar.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos consultar la dirección del punto."); }
    finally { setBusy(false); }
  };
  const confirm = async (choice: "written" | "reverse") => {
    if (!current || !point) return;
    setBusy(true); setError("");
    try {
      const confirmed = await apiRequest<Address>(`/addresses/${current.id}/confirm/`, { method: "POST", body: JSON.stringify(buildAddressConfirmation(point.latitude, point.longitude, choice)) });
      selectAddress(confirmed); setMessage("Dirección confirmada y lista para cotizar el envío."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos confirmar la dirección."); }
    finally { setBusy(false); }
  };
  const far = Boolean(origin && point && requiresReverseLookup(origin.latitude, origin.longitude, point.latitude, point.longitude));

  return <div className="address-layout">
    <section><h2>Direcciones guardadas</h2>{addresses.length ? addresses.map((address) => <button type="button" className="address-row" key={address.id} onClick={() => selectAddress(address)}><strong>{address.label}</strong><span>{address.raw_address}</span><small>{address.needs_review ? "Requiere confirmación" : "Confirmada"}</small></button>) : <p>No hay direcciones guardadas.</p>}</section>
    <form className="form-stack address-form" onSubmit={(event) => void save(event)}><h2>Nueva dirección</h2><div className="postal-row"><div><label htmlFor="postal">CP o CPA</label><input id="postal" value={values.postal_code} onChange={(event) => setValues({ ...values, postal_code: event.target.value.toUpperCase() })} required /></div><button className="button secondary" type="button" onClick={() => void postalLookup()}>Buscar localidad</button></div>{localities.length > 0 && <><label htmlFor="locality">Localidad y provincia</label><select id="locality" value={`${values.locality}|${values.province}`} onChange={(event) => { const [locality, province] = event.target.value.split("|"); const row = localities.find((item) => item.locality === locality && item.province === province); setValues({ ...values, locality, province, cpa: row?.cpa ?? "" }); }}>{localities.map((row) => <option key={`${row.locality}-${row.province}`} value={`${row.locality}|${row.province}`}>{row.locality}, {row.province}</option>)}</select></>}<div className="field-pair"><div><label htmlFor="street">Calle</label><input id="street" value={values.street} onChange={(event) => setValues({ ...values, street: event.target.value })} required /></div><div><label htmlFor="number">Número</label><input id="number" value={values.number} onChange={(event) => setValues({ ...values, number: event.target.value })} required /></div></div><div className="field-pair"><div><label htmlFor="floor">Piso</label><input id="floor" value={values.floor} onChange={(event) => setValues({ ...values, floor: event.target.value })} /></div><div><label htmlFor="apartment">Departamento</label><input id="apartment" value={values.apartment} onChange={(event) => setValues({ ...values, apartment: event.target.value })} /></div></div><label htmlFor="notes">Notas para la entrega</label><textarea id="notes" value={values.notes} onChange={(event) => setValues({ ...values, notes: event.target.value })} /><button className="button primary" disabled={busy}>{busy ? "Guardando…" : "Guardar y ubicar"}</button></form>
    {error && <p className="inline-error" role="alert">{error}</p>}{message && <p ref={messageRef} tabIndex={-1} className="success-message" role="status">{message}</p>}
    {current && point && <section className="map-confirmation" aria-labelledby="map-confirmation-title"><div><h2 id="map-confirmation-title">Confirmá el punto de entrega</h2><p><strong>Dirección escrita:</strong> {writtenAddress}</p>{reverseAddress && <p><strong>Dirección encontrada:</strong> {reverseAddress}</p>}</div><AddressMap latitude={point.latitude} longitude={point.longitude} onMove={(latitude, longitude) => { setPoint({ latitude, longitude }); setLatitudeInput(String(latitude)); setLongitudeInput(String(longitude)); setReverseAddress(""); }} /><details className="coordinate-editor"><summary>Ajustar manualmente (opcional)</summary><div className="field-pair"><div><label htmlFor="latitude">Ubicación norte/sur</label><input id="latitude" type="text" inputMode="decimal" value={latitudeInput} onChange={(event) => { const value = event.target.value; setLatitudeInput(value); const latitude = Number(value); if (value && Number.isFinite(latitude)) setPoint({ ...point, latitude }); }} /></div><div><label htmlFor="longitude">Ubicación este/oeste</label><input id="longitude" type="text" inputMode="decimal" value={longitudeInput} onChange={(event) => { const value = event.target.value; setLongitudeInput(value); const longitude = Number(value); if (value && Number.isFinite(longitude)) setPoint({ ...point, longitude }); }} /></div></div></details>{current.needs_review ? far && !reverseAddress ? <div className="map-warning"><strong>El punto quedó lejos de la dirección escrita.</strong><p>Buscá la dirección de ese punto y después elegí cuál conservar.</p><button className="button primary" disabled={busy} onClick={() => void reverse()}>Buscar dirección del punto</button></div> : reverseAddress ? <div className="confirmation-choices"><button className="button secondary" disabled={busy} onClick={() => void confirm("written")}>Usar dirección escrita</button><button className="button primary" disabled={busy} onClick={() => void confirm("reverse")}>Usar dirección encontrada</button></div> : <div className="inline-notice"><p>El punto coincide con la dirección. Confirmalo para continuar.</p><button className="button primary" disabled={busy} onClick={() => void confirm("written")}>Confirmar esta dirección</button></div> : <p className="success-message">Esta dirección ya está confirmada{current.reviewed_at ? ` desde el ${new Date(current.reviewed_at).toLocaleString("es-AR")}` : ""}.</p>}</section>}
  </div>;
}
