"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { BillingProfile, Customer, Order } from "@/lib/types";

export function AccountDashboard() {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [billing, setBilling] = useState<BillingProfile[]>([]);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    Promise.all([
      apiRequest<Customer>("/customers/me/"),
      apiRequest<Order[]>("/orders/"),
      apiRequest<BillingProfile[]>("/billing-profiles/"),
    ])
      .then(([me, orderRows, billingRows]) => {
        setCustomer(me);
        setOrders(orderRows);
        setBilling(billingRows);
      })
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "Iniciá sesión para ver tu cuenta."),
      );
  }, []);

  const logout = async () => {
    setLoggingOut(true);
    try {
      await apiRequest<void>("/auth/logout/", { method: "POST" });
      window.location.assign("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos cerrar la sesión.");
      setLoggingOut(false);
    }
  };

  if (error) {
    return (
      <div className="empty-state">
        <h2>Tu cuenta necesita una sesión activa</h2>
        <p>{error}</p>
        <Link className="button primary" href="/cuenta/ingresar">Ingresar</Link>
      </div>
    );
  }
  if (!customer) return <div className="account-skeleton" role="status">Cargando tu cuenta…</div>;

  return (
    <div className="account-grid">
      <section className="account-panel">
        <div className="section-heading">
          <h2>Perfil</h2>
          <button className="text-button" type="button" disabled={loggingOut} onClick={() => void logout()}>
            {loggingOut ? "Cerrando…" : "Cerrar sesión"}
          </button>
        </div>
        <dl>
          <div><dt>Email</dt><dd>{customer.email}</dd></div>
          <div><dt>Verificación</dt><dd>{customer.email_verified_at ? "Email verificado" : "Pendiente"}</dd></div>
          <div><dt>Nombre</dt><dd>{[customer.profile.first_name, customer.profile.last_name].filter(Boolean).join(" ") || "No informado"}</dd></div>
          <div><dt>Teléfono</dt><dd>{customer.profile.phone || "No informado"}</dd></div>
        </dl>
        <p className="helper">El contrato actual permite consultar el perfil. La edición todavía no está publicada por la API.</p>
      </section>
      <section className="account-panel">
        <div className="section-heading"><h2>Datos fiscales</h2><Link href="/cuenta/fiscal">Administrar</Link></div>
        {billing.length ? billing.map((profile) => (
          <p key={profile.id}><strong>{profile.label}</strong><br />{profile.legal_name} · {profile.masked_cuit}</p>
        )) : <p>No tenés perfiles fiscales guardados.</p>}
      </section>
      <section className="account-panel account-orders">
        <div className="section-heading"><h2>Pedidos</h2><Link href="/cuenta/direcciones">Direcciones</Link></div>
        {orders.length ? orders.map((order) => (
          <Link className="order-row" key={order.public_id} href={`/pedidos/${order.public_id}`}>
            <span>Pedido {order.public_id.slice(0, 8)}</span><span>{order.payment_status}</span><strong>{formatMoney(order.total_snapshot)}</strong>
          </Link>
        )) : <div className="empty-compact"><p>Todavía no hay pedidos.</p><Link href="/catalogo">Explorar catálogo</Link></div>}
      </section>
    </div>
  );
}
