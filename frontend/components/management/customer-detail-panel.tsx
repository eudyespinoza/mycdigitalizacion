"use client";

import {
  CheckCircle,
  IdentificationCard,
  MapPin,
  PencilSimple,
  Receipt,
  UserCircle,
} from "@phosphor-icons/react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { ManagementOrderTable } from "@/components/management/order-table";
import { ManagementFormDialog } from "@/components/ui/management-form-dialog";
import { formatMoney } from "@/lib/format";
import { managementRequest } from "@/lib/management/api";
import type { ManagementCustomerDetail } from "@/lib/management/operations-types";


type CustomerAddress = ManagementCustomerDetail["addresses"][number];

const taxConditionLabels: Record<string, string> = {
  consumidor_final: "Consumidor final",
  exento: "Exento",
  monotributista: "Monotributista",
  responsable_inscripto: "Responsable inscripto",
};


function valueOrFallback(value: string, fallback = "Sin cargar") {
  return value.trim() || fallback;
}


export function CustomerDetailPanel({ initial }: { initial: ManagementCustomerDetail }) {
  const [customer, setCustomer] = useState(initial);
  const [contactOpen, setContactOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<CustomerAddress | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const updateContact = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const dni = String(data.get("dni") ?? "").trim();
    setSaving(true);
    setError("");
    try {
      const updated = await managementRequest<ManagementCustomerDetail>(`/customers/${customer.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          first_name: String(data.get("first_name") ?? ""),
          last_name: String(data.get("last_name") ?? ""),
          email: String(data.get("email") ?? ""),
          phone: String(data.get("phone") ?? ""),
          ...(dni ? { dni } : {}),
        }),
      });
      setCustomer(updated);
      setContactOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos actualizar el cliente.");
    } finally {
      setSaving(false);
    }
  };

  const updateAddress = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingAddress) return;
    const data = new FormData(event.currentTarget);
    const street = String(data.get("street") ?? "").trim();
    const number = String(data.get("number") ?? "").trim();
    setSaving(true);
    setError("");
    try {
      const updated = await managementRequest<CustomerAddress>(
        `/customers/${customer.id}/addresses/${editingAddress.id}/`,
        {
          method: "PATCH",
          body: JSON.stringify({
            label: String(data.get("label") ?? ""),
            raw_address: `${street} ${number}`.trim(),
            normalized_address: `${street} ${number}`.trim(),
            street,
            number,
            postal_code: String(data.get("postal_code") ?? ""),
            cpa: String(data.get("cpa") ?? ""),
            locality: String(data.get("locality") ?? ""),
            province: String(data.get("province") ?? ""),
            floor: String(data.get("floor") ?? ""),
            apartment: String(data.get("apartment") ?? ""),
            reference: String(data.get("reference") ?? ""),
            notes: String(data.get("notes") ?? ""),
            needs_review: data.get("needs_review") === "on",
          }),
        },
      );
      setCustomer((current) => ({
        ...current,
        addresses: current.addresses.map((address) => address.id === updated.id ? updated : address),
      }));
      setEditingAddress(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No pudimos actualizar la dirección.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="management-page customer-detail-page">
      <Link className="management-back" href="/gestion/clientes">← Volver a clientes</Link>
      <header className="management-page-header customer-detail-header">
        <div>
          <h1>{customer.name}</h1>
          <p>{customer.email} · {valueOrFallback(customer.phone, "Sin teléfono")}</p>
        </div>
        <button className="button primary" onClick={() => { setError(""); setContactOpen(true); }} type="button">
          <PencilSimple aria-hidden="true" size={18} weight="bold" />
          Editar cliente
        </button>
      </header>

      <dl className="customer-summary-list">
        <div>
          <dt><UserCircle aria-hidden="true" size={18} />Contacto</dt>
          <dd>{valueOrFallback(customer.phone, "Sin teléfono")}</dd>
        </div>
        <div>
          <dt><IdentificationCard aria-hidden="true" size={18} />DNI</dt>
          <dd>{valueOrFallback(customer.masked_dni)}</dd>
        </div>
        <div>
          <dt><Receipt aria-hidden="true" size={18} />Actividad</dt>
          <dd>{customer.order_count} {customer.order_count === 1 ? "pedido" : "pedidos"} · {formatMoney(customer.total_spent)}</dd>
        </div>
        <div>
          <dt><CheckCircle aria-hidden="true" size={18} />Email</dt>
          <dd><span className={`management-pill ${customer.email_verified ? "is-live" : "is-draft"}`}>{customer.email_verified ? "Verificado" : "Pendiente"}</span></dd>
        </div>
      </dl>

      <div className="customer-information-grid">
        <section className="management-form-section customer-addresses-section">
          <div className="management-section-heading">
            <div><h2>Direcciones</h2><p>Datos utilizados para entrega y geolocalización.</p></div>
            <MapPin aria-hidden="true" className="customer-section-icon" size={24} />
          </div>
          {customer.addresses.length ? <div className="customer-address-list">{customer.addresses.map((address) => (
            <article className="customer-address" key={address.id}>
              <header>
                <div>
                  <h3>{address.label}</h3>
                  <span className={`management-pill ${address.needs_review ? "is-review" : "is-live"}`}>{address.needs_review ? "Revisar ubicación" : "Ubicación confirmada"}</span>
                </div>
                <button aria-label={`Editar dirección ${address.label}`} className="customer-edit-button" onClick={() => { setError(""); setEditingAddress(address); }} type="button">
                  <PencilSimple aria-hidden="true" size={17} weight="bold" />
                  Editar
                </button>
              </header>
              <address>
                <strong>{address.normalized_address || address.raw_address}</strong>
                {(address.floor || address.apartment) ? <span>{address.floor ? `Piso ${address.floor}` : "Sin piso"}{address.apartment ? ` · Depto. ${address.apartment}` : ""}</span> : null}
                <span>{address.locality} · {address.province}</span>
                <span>CP {address.postal_code}{address.cpa ? ` · CPA ${address.cpa}` : ""}</span>
              </address>
              {address.reference ? <p><b>Referencia:</b> {address.reference}</p> : null}
              {address.notes ? <p><b>Observaciones:</b> {address.notes}</p> : null}
            </article>
          ))}</div> : <p>No tiene direcciones cargadas.</p>}
        </section>

        <section className="management-form-section customer-billing-section">
          <div className="management-section-heading"><div><h2>Datos fiscales</h2><p>Perfiles disponibles para facturación.</p></div></div>
          {customer.billing_profiles.length ? <div className="customer-billing-list">{customer.billing_profiles.map((profile) => (
            <article key={profile.id}>
              <div><h3>{profile.label}</h3>{profile.is_default ? <span className="management-pill is-live">Predeterminado</span> : null}</div>
              <strong>{profile.legal_name}</strong>
              <span>{taxConditionLabels[profile.tax_condition] ?? profile.tax_condition}</span>
              <span>{valueOrFallback(profile.masked_cuit, "CUIT sin cargar")}</span>
            </article>
          ))}</div> : <p>No tiene perfiles fiscales.</p>}
        </section>
      </div>

      <section className="management-form-section customer-orders-section">
        <div className="management-section-heading"><div><h2>Pedidos</h2><p>Historial de compras y estado de cada operación.</p></div></div>
        <ManagementOrderTable orders={customer.orders} />
      </section>

      <ManagementFormDialog
        description="Actualizá los datos del cliente. El DNI/NIF sólo se reemplaza si ingresás uno nuevo."
        onClose={() => { if (!saving) setContactOpen(false); }}
        open={contactOpen}
        title="Editar cliente"
      >
        <form className="compact-management-form" onSubmit={(event) => void updateContact(event)}>
          <div className="management-field-grid">
            <label><span>Nombre</span><input defaultValue={customer.first_name} name="first_name" required /></label>
            <label><span>Apellido</span><input defaultValue={customer.last_name} name="last_name" required /></label>
            <label><span>Email</span><input defaultValue={customer.email} name="email" required type="email" /></label>
            <label><span>Teléfono</span><input defaultValue={customer.phone} name="phone" type="tel" /></label>
            <label className="field-wide"><span>DNI / NIF</span><input inputMode="numeric" name="dni" pattern="[0-9 .-]{8,14}" placeholder={customer.masked_dni || "Ingresá 8 dígitos"} /></label>
          </div>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions">
            <button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar cambios"}</button>
            <button className="button secondary" disabled={saving} onClick={() => setContactOpen(false)} type="button">Cancelar</button>
          </div>
        </form>
      </ManagementFormDialog>

      <ManagementFormDialog
        description="Corregí los datos escritos sin exponer coordenadas ni información sensible."
        onClose={() => { if (!saving) setEditingAddress(null); }}
        open={Boolean(editingAddress)}
        size="wide"
        title="Editar dirección"
      >
        {editingAddress ? <form className="compact-management-form" onSubmit={(event) => void updateAddress(event)}>
          <div className="management-field-grid">
            <label><span>Etiqueta</span><input defaultValue={editingAddress.label} name="label" required /></label>
            <label><span>Calle</span><input defaultValue={editingAddress.street} name="street" required /></label>
            <label><span>Altura</span><input defaultValue={editingAddress.number} name="number" required /></label>
            <label><span>Código postal</span><input defaultValue={editingAddress.postal_code} name="postal_code" required /></label>
            <label><span>CPA</span><input defaultValue={editingAddress.cpa} name="cpa" /></label>
            <label><span>Localidad</span><input defaultValue={editingAddress.locality} name="locality" required /></label>
            <label><span>Provincia</span><input defaultValue={editingAddress.province} name="province" required /></label>
            <label><span>Piso</span><input defaultValue={editingAddress.floor} name="floor" /></label>
            <label><span>Departamento</span><input defaultValue={editingAddress.apartment} name="apartment" /></label>
            <label className="field-wide"><span>Referencia</span><input defaultValue={editingAddress.reference} name="reference" /></label>
            <label className="field-wide"><span>Observaciones</span><textarea defaultValue={editingAddress.notes} name="notes" rows={3} /></label>
            <label className="management-check field-wide"><input defaultChecked={editingAddress.needs_review} name="needs_review" type="checkbox" /><span>Requiere revisión logística</span></label>
          </div>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="management-form-actions">
            <button className="button primary" disabled={saving} type="submit">{saving ? "Guardando…" : "Guardar dirección"}</button>
            <button className="button secondary" disabled={saving} onClick={() => setEditingAddress(null)} type="button">Cancelar</button>
          </div>
        </form> : null}
      </ManagementFormDialog>
    </div>
  );
}
