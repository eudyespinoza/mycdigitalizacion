"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Address, BillingProfile, CheckoutResponse, ShippingQuote } from "@/lib/types";

export type CheckoutUiState = "idle" | "checking" | "pending_review" | "provider_down" | "approved" | "rejected";

export function getTrustedOrderState(_params: URLSearchParams, serverPaymentStatus: string | null): CheckoutUiState {
  if (!serverPaymentStatus) return "checking";
  if (serverPaymentStatus === "approved") return "approved";
  if (["rejected", "cancelled"].includes(serverPaymentStatus)) return "rejected";
  return "checking";
}

export function CheckoutStatePanel({ state }: { state: CheckoutUiState }) {
  const copy = {
    idle: ["Listo para continuar", "Revisá los datos antes de confirmar."],
    checking: ["Estamos consultando tu pedido", "La confirmación proviene del servidor, no de la URL de regreso."],
    pending_review: ["Validación en revisión", "No reservamos stock ni iniciamos el pago hasta que termine la revisión."],
    provider_down: ["Servicio no disponible", "El proveedor no respondió. Intentá nuevamente más tarde."],
    approved: ["Pago aprobado", "El servidor confirmó el pago."],
    rejected: ["Pago no aprobado", "Podés revisar el pedido e intentar nuevamente cuando la API lo permita."],
  }[state];
  return <section className={`state-panel state-${state}`} aria-live="polite"><h2>{copy[0]}</h2><p>{copy[1]}</p></section>;
}

export function CheckoutFlow() {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<CheckoutUiState>("idle");
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [billing, setBilling] = useState<BillingProfile[]>([]);
  const [addressId, setAddressId] = useState(0);
  const [billingId, setBillingId] = useState(0);
  const [method, setMethod] = useState<"shipping" | "pickup">("shipping");
  const [quote, setQuote] = useState<ShippingQuote | null>(null);
  const [error, setError] = useState("");

  const loadAccount = async () => {
    try {
      const [addressRows, billingRows] = await Promise.all([apiRequest<Address[]>("/addresses/"), apiRequest<BillingProfile[]>("/billing-profiles/")]);
      setAddresses(addressRows); setBilling(billingRows); setAddressId(addressRows[0]?.id ?? 0); setBillingId(billingRows[0]?.id ?? 0); setStep(1);
    } catch { setError("Iniciá sesión y verificá tu email para continuar."); }
  };
  const getQuote = async () => {
    if (method === "pickup") { setStep(3); return; }
    try { setQuote(await apiRequest<ShippingQuote>("/shipping/quote/", { method: "POST", body: JSON.stringify({ address_id: addressId }) })); setStep(3); }
    catch (cause) { setState("provider_down"); setError(cause instanceof Error ? cause.message : "No pudimos cotizar el envío."); }
  };
  const confirm = async () => {
    setError("");
    try {
      const payload = { fulfillment_method: method, billing_profile_id: billingId, consent: true, idempotency_key: crypto.randomUUID(), ...(method === "shipping" ? { address_id: addressId, shipping_quote_id: quote?.public_id } : {}) };
      const result = await apiRequest<CheckoutResponse>("/checkout/", { method: "POST", body: JSON.stringify(payload) });
      if (!result.checkout_url) { setState("pending_review"); return; }
      window.location.assign(result.checkout_url);
    } catch (cause) { setState("provider_down"); setError(cause instanceof Error ? cause.message : "No pudimos iniciar el pago."); }
  };

  const steps = ["Cuenta e identidad", "Entrega", "Envío", "Revisión"];
  return <div className="checkout-layout"><ol className="checkout-stepper" aria-label="Progreso del checkout">{steps.map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined} className={index <= step ? "active" : ""}><span>{index + 1}</span>{label}</li>)}</ol>{error && <p className="inline-error" role="alert">{error}</p>}{state !== "idle" && <CheckoutStatePanel state={state} />}{step === 0 && <section className="checkout-stage"><h2>Cuenta e identidad</h2><p>La API valida tu sesión, email e identidad antes de reservar stock o iniciar el pago.</p><button className="button primary" onClick={() => void loadAccount()}>Validar cuenta</button></section>}{step === 1 && <section className="checkout-stage"><h2>Elegí cómo recibir</h2><label><input type="radio" name="method" checked={method === "shipping"} onChange={() => setMethod("shipping")} /> Envío a domicilio</label><label><input type="radio" name="method" checked={method === "pickup"} onChange={() => setMethod("pickup")} /> Retiro</label>{method === "shipping" && <select aria-label="Dirección" value={addressId} onChange={(event) => setAddressId(Number(event.target.value))}>{addresses.map((address) => <option key={address.id} value={address.id}>{address.label}: {address.raw_address}</option>)}</select>}<a href="/cuenta/direcciones">Agregar o confirmar dirección</a><button className="button primary" onClick={() => setStep(2)} disabled={method === "shipping" && !addressId}>Continuar</button></section>}{step === 2 && <section className="checkout-stage"><h2>Confirmá el envío</h2><p>{method === "pickup" ? "El retiro no requiere cotización de correo." : "Consultaremos un precio real y su vencimiento con el proveedor."}</p><button className="button primary" onClick={() => void getQuote()}>{method === "pickup" ? "Continuar" : "Cotizar envío"}</button></section>}{step === 3 && <section className="checkout-stage"><h2>Revisá antes de pagar</h2>{quote && <p>Envío: {quote.currency} {quote.total_amount}. Vigente hasta {new Date(quote.expires_at).toLocaleString("es-AR")}.</p>}<label htmlFor="billing">Perfil fiscal</label><select id="billing" value={billingId} onChange={(event) => setBillingId(Number(event.target.value))}>{billing.map((profile) => <option key={profile.id} value={profile.id}>{profile.label} · {profile.masked_cuit}</option>)}</select><p>Mercado Pago abrirá en su sitio. El pedido solo se considera pagado cuando el servidor lo confirme.</p><button className="button primary" disabled={!billingId} onClick={() => void confirm()}>Ir a Mercado Pago</button></section>}</div>;
}
