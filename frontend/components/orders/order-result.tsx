"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { CheckoutStatePanel, getTrustedOrderState, type CheckoutUiState } from "@/components/checkout/checkout-flow";

export async function pollPaymentStatus(request: () => Promise<string>, options: { attempts: number; intervalMs: number }) {
  let status = "pending";
  for (let attempt = 1; attempt <= options.attempts; attempt += 1) {
    status = await request();
    if (!["pending", "in_process", "checking"].includes(status)) return { status, attempts: attempt };
    if (attempt < options.attempts && options.intervalMs > 0) await new Promise((resolve) => setTimeout(resolve, options.intervalMs));
  }
  return { status, attempts: options.attempts };
}

export function OrderResult({ search }: { search: string }) {
  const reference = new URLSearchParams(search).get("external_reference"); const [state, setState] = useState<CheckoutUiState>("checking"); const [error, setError] = useState(""); const [polling, setPolling] = useState(false); const [exhausted, setExhausted] = useState(false);
  const check = useCallback(async () => {
    if (!reference) { setError("No recibimos una referencia para consultar. Revisá el pedido desde tu cuenta."); return; }
    setPolling(true); setError(""); setExhausted(false);
    try {
      const result = await pollPaymentStatus(async () => (await apiRequest<{ status: string }>(`/payments/${encodeURIComponent(reference)}/status/`)).status, { attempts: 6, intervalMs: 1500 });
      setState(getTrustedOrderState(new URLSearchParams(search), result.status)); setExhausted(["pending", "in_process"].includes(result.status));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos consultar el pago."); }
    finally { setPolling(false); }
  }, [reference, search]);
  useEffect(() => { void check(); }, [check]);
  return <div className="result-page"><CheckoutStatePanel state={state} />{polling && <p role="status">Consultando la confirmación del servidor…</p>}{error && <p className="inline-error" role="alert">{error}</p>}{exhausted && <div className="inline-notice"><p>El pago todavía está pendiente. Podés consultar de nuevo sin duplicar la operación.</p><button className="button secondary" disabled={polling} onClick={() => void check()}>Consultar nuevamente</button></div>}<p>Los parámetros de regreso de Mercado Pago nunca se usan como aprobación. Esta pantalla consulta el estado autenticado del servidor.</p><div className="checkout-actions">{reference && <Link className="button primary" href={`/pedidos/${encodeURIComponent(reference)}`}>Ver este pedido</Link>}<Link className="button secondary" href="/cuenta">Ver mis pedidos</Link></div></div>;
}
