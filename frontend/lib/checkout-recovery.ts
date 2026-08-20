import type { CheckoutUiState } from "@/components/checkout/checkout-flow";

type CheckoutRecovery = { step: number; state: CheckoutUiState; message: string };
const recoveries: Record<string, CheckoutRecovery> = {
  empty_cart: { step: 3, state: "idle", message: "El carrito está vacío. Agregá productos antes de confirmar." },
  identity_missing: { step: 0, state: "idle", message: "Completá y guardá tu DNI para continuar." },
  email_not_verified: { step: 0, state: "idle", message: "Verificá tu email antes de continuar." },
  identity_pending_review: { step: 0, state: "pending_review", message: "Estamos verificando tus datos. Te avisaremos cuando puedas continuar." },
  identity_rejected: { step: 0, state: "rejected", message: "No pudimos verificar tus datos. Revisalos antes de volver a intentar." },
  billing_profile_invalid: { step: 3, state: "idle", message: "Elegí o actualizá un perfil fiscal válido." },
  address_required: { step: 1, state: "idle", message: "Elegí una dirección de entrega." },
  address_review_required: { step: 1, state: "idle", message: "Confirmá el punto de entrega antes de continuar." },
  pickup_unavailable: { step: 1, state: "idle", message: "El retiro no está disponible. Elegí una dirección de entrega." },
  invalid_fulfillment: { step: 1, state: "idle", message: "Elegí nuevamente cómo querés recibir la compra." },
  shipping_quote_required: { step: 2, state: "idle", message: "Cotizá el envío antes de confirmar." },
  shipping_quote_expired: { step: 2, state: "idle", message: "La cotización venció. Pedí una nueva para continuar." },
  shipping_quote_changed: { step: 2, state: "idle", message: "La cotización cambió. Revisá el envío y confirmá el nuevo importe." },
  identity_consent_required: { step: 0, state: "idle", message: "Aceptá la validación de identidad para continuar." },
  invalid_email: { step: 0, state: "idle", message: "Corregí el email de tu cuenta antes de continuar." },
  cart_owner_mismatch: { step: 0, state: "idle", message: "Volvé a iniciar sesión para asociar el carrito a tu cuenta." },
  insufficient_stock: { step: 3, state: "idle", message: "Cambió el stock del carrito. Revisá las cantidades antes de confirmar." },
  checkout_changed: { step: 3, state: "idle", message: "La compra cambió. Revisá nuevamente los productos, la entrega y el total." },
};
const unavailableProviderCodes = new Set(["not_configured", "unavailable", "timeout"]);
export function checkoutRecoveryFor(code: string, currentStep = 3): CheckoutRecovery {
  if (unavailableProviderCodes.has(code)) return { step: currentStep, state: "provider_down", message: "No pudimos completar este paso. Guardamos tus datos para que vuelvas a intentar." };
  if (code === "rejected") return { step: currentStep, state: "rejected", message: "No pudimos completar la operación. Revisá los datos antes de volver a intentar." };
  if (code === "invalid_response") return { step: currentStep, state: "needs_attention", message: "Estamos revisando este paso. Guardamos tus datos y te avisaremos si hace falta algo más." };
  if (code === "not_supported") return { step: currentStep, state: "needs_attention", message: "Esta opción no está disponible. Elegí otra alternativa o retomá el pedido desde tu cuenta." };
  return recoveries[code] ?? { step: 3, state: "idle", message: "Revisá los datos e intentá nuevamente." };
}
