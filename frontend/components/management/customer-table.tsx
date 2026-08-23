import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { ManagementCustomer } from "@/lib/management/operations-types";


export function ManagementCustomerTable({ customers }: { customers: ManagementCustomer[] }) {
  if (!customers.length) return <div className="management-empty"><h2>No hay clientes</h2><p>Los registros nuevos aparecerán acá.</p></div>;
  return (
    <div className="management-table-wrap">
      <table className="management-table">
        <thead><tr><th>Cliente</th><th>Contacto</th><th>Identidad</th><th>Actividad</th><th>Email</th></tr></thead>
        <tbody>{customers.map((customer) => <tr className="management-customer-row" key={customer.id}>
          <td><Link aria-label={`Abrir ficha completa de ${customer.name}`} className="management-customer-row-link" href={`/gestion/clientes/${customer.id}`}>{customer.name}</Link></td>
          <td><span className="management-contact-cell">{customer.email}<small>{customer.phone || "Sin teléfono"}</small></span></td>
          <td><span className="management-identity-cell">DNI <strong>{customer.masked_dni || "Sin cargar"}</strong></span></td>
          <td><span className="management-activity-cell"><strong>{customer.order_count} {customer.order_count === 1 ? "pedido" : "pedidos"}</strong><small>{formatMoney(customer.total_spent)}</small></span></td>
          <td><span className={`management-pill ${customer.email_verified ? "is-live" : "is-draft"}`}>{customer.email_verified ? "Verificado" : "Pendiente"}</span></td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
