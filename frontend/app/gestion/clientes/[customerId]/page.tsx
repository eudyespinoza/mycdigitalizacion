import Link from "next/link";

import { ManagementOrderTable } from "@/components/management/order-table";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementCustomerDetail } from "@/lib/management/operations-types";


export default async function ManagementCustomerPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = await params;
  const customer = await managementServerGet<ManagementCustomerDetail>(`/customers/${customerId}/`);
  return <div className="management-page management-editor-page"><Link className="management-back" href="/gestion/clientes">← Volver a clientes</Link><header className="management-page-header"><div><p className="management-kicker">Cliente</p><h1>{customer.name}</h1><p>{customer.email} · {customer.phone || "Sin teléfono"} · DNI {customer.masked_dni || "sin cargar"}</p></div></header><div className="management-detail-grid"><section className="management-form-section"><h2>Direcciones</h2>{customer.addresses.length ? <ul className="management-simple-list">{customer.addresses.map((address) => <li key={address.id}><strong>{address.label}</strong><span>{address.raw_address}, {address.locality}</span></li>)}</ul> : <p>No tiene direcciones cargadas.</p>}</section><section className="management-form-section"><h2>Datos fiscales</h2>{customer.billing_profiles.length ? <ul className="management-simple-list">{customer.billing_profiles.map((profile) => <li key={profile.id}><strong>{profile.legal_name}</strong><span>{profile.tax_condition} · {profile.masked_cuit}</span></li>)}</ul> : <p>No tiene perfiles fiscales.</p>}</section><section className="management-detail-wide"><h2>Pedidos</h2><ManagementOrderTable orders={customer.orders} /></section></div></div>;
}
