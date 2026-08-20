import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { ManagementCustomer } from "@/lib/management/operations-types";


export function ManagementCustomerTable({ customers }: { customers: ManagementCustomer[] }) {
  if (!customers.length) return <div className="management-empty"><h2>No hay clientes</h2><p>Los registros nuevos aparecerán acá.</p></div>;
  return (
    <div className="management-table-wrap">
      <table className="management-table">
        <thead><tr><th>Cliente</th><th>Contacto</th><th>DNI</th><th>Pedidos</th><th>Total histórico</th><th>Email</th></tr></thead>
        <tbody>{customers.map((customer) => <tr key={customer.id}>
          <td><Link href={`/gestion/clientes/${customer.id}`}>{customer.name}</Link></td>
          <td>{customer.email}<small>{customer.phone || "Sin teléfono"}</small></td>
          <td>{customer.masked_dni || "Sin cargar"}</td>
          <td>{customer.order_count}</td>
          <td>{formatMoney(customer.total_spent)}</td>
          <td><span className={`management-pill ${customer.email_verified ? "is-live" : "is-draft"}`}>{customer.email_verified ? "Verificado" : "Pendiente"}</span></td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
