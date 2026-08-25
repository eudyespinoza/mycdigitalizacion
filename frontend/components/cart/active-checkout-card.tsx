import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { Cart } from "@/lib/types";

type ActiveCheckout = NonNullable<Cart["active_checkout"]>;

export function ActiveCheckoutCard({ checkout }: { checkout: ActiveCheckout }) {
  const waitingForShipping = checkout.shipping_cost_status === "pending_agreement";
  return (
    <section className="active-checkout-card" aria-label="Compra en curso">
      <span>Compra en curso</span>
      <strong>
        {waitingForShipping
          ? "Estamos coordinando el envío"
          : "Tu pedido ya tiene la entrega configurada"}
      </strong>
      <p>
        {waitingForShipping
          ? "Te avisaremos cuando el costo esté listo."
          : "Continuá el pago sin volver a cargar tus datos."}
      </p>
      {!waitingForShipping && <p>Envío: {formatMoney(checkout.shipping_amount)}</p>}
      <p>Total: {waitingForShipping ? "A confirmar" : formatMoney(checkout.total)}</p>
      <Link className="button primary wide" href={`/pedidos/${checkout.order_id}`}>
        {checkout.can_resume ? "Continuar pedido" : "Ver pedido"}
      </Link>
    </section>
  );
}
