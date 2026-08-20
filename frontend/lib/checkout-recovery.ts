import type { CheckoutUiState } from "@/components/checkout/checkout-flow";

type CheckoutRecovery = { step: number; state: CheckoutUiState; message: string };
const recoveries: Record<string, CheckoutRecovery> = {
  empty_cart: { step: 3, state: "idle", message: "El carrito está vacío. Agregá productos antes de confirmar." },
  identity_missing: { step: 0, state: "idle", message: "Completá y guardá tu DNI para continuar." },
  email_unverified: { step: 0, state: "idle", message: "Verificá tu email antes de continuar." },
  identity_pending_review: { step: 0, state: "pending_review", message: "Tu identidad está en revisión. No reservamos stock ni iniciamos el pago." },
  identity_rejected: { step: 0, state: "rejected", message: "La validación de identidad necesita una corrección." },
  billing_profile_required: { step: 3, state: "idle", message: "Elegí o creá un perfil fiscal." },
  address_required: { step: 1, state: "idle", message: "Elegí una dirección de entrega." },
  address_unconfirmed: { step: 1, state: "idle", message: "Confirmá el punto de entrega antes de continuar." },
  shipping_quote_required: { step: 2, state: "idle", message: "Cotizá el envío antes de confirmar." },
  shipping_quote_expired: { step: 2, state: "idle", message: "La cotización venció. Pedí una nueva para continuar." },
  provider_down: { step: 2, state: "provider_down", message: "El proveedor no está disponible. Conservamos tus datos para reintentar." },
};
export function checkoutRecoveryFor(code: string): CheckoutRecovery {
  return recoveries[code] ?? { step: 3, state: "idle", message: "Revisá los datos e intentá nuevamente." };
}
