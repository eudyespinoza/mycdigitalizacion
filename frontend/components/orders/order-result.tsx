"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { CheckoutStatePanel, getTrustedOrderState, type CheckoutUiState } from "@/components/checkout/checkout-flow";

export function OrderResult({ search }: { search: string }) {
  const [state, setState] = useState<CheckoutUiState>("checking"); const [error, setError] = useState("");
  useEffect(() => { const params = new URLSearchParams(search); const reference = params.get("external_reference"); if (!reference) { setError("No recibimos una referencia para consultar. Revisá el pedido desde tu cuenta."); return; } apiRequest<{ status: string }>(`/payments/${encodeURIComponent(reference)}/status/`).then((result) => setState(getTrustedOrderState(params, result.status))).catch((cause) => setError(cause instanceof Error ? cause.message : "No pudimos consultar el pago.")); }, [search]);
  return <div className="result-page"><CheckoutStatePanel state={state} />{error && <p className="inline-error" role="alert">{error}</p>}<p>Los parámetros de regreso de Mercado Pago nunca se usan como aprobación. Esta pantalla consulta el estado autenticado del servidor.</p><Link className="button primary" href="/cuenta">Ver mis pedidos</Link></div>;
}
