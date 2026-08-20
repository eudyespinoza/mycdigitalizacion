"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import { checkoutRecoveryFor } from "@/lib/checkout-recovery";
import { formatMoney } from "@/lib/format";
import { useCart } from "@/components/cart/cart-provider";
import type { Address, BillingProfile, CheckoutResponse, Customer, IdentityStatus, ShippingQuote, StorefrontHome } from "@/lib/types";

export type CheckoutUiState = "idle" | "checking" | "pending_review" | "provider_down" | "approved" | "rejected" | "refunded" | "needs_attention";

export function getTrustedOrderState(_params: URLSearchParams, serverPaymentStatus: string | null): CheckoutUiState {
  if (!serverPaymentStatus || ["not_started", "pending"].includes(serverPaymentStatus)) return "checking";
  if (serverPaymentStatus === "paid") return "approved";
  if (serverPaymentStatus === "failed") return "rejected";
  if (serverPaymentStatus === "refunded") return "refunded";
  if (serverPaymentStatus === "needs_attention") return "needs_attention";
  return "checking";
}

export function CheckoutStatePanel({ state }: { state: CheckoutUiState }) {
  const copy = {
    idle: ["Listo para continuar", "Revisá los datos antes de confirmar."],
    checking: ["Estamos consultando tu pedido", "La confirmación proviene del servidor, no de la URL de regreso."],
    pending_review: ["Validación en revisión", "No reservamos stock ni iniciamos el pago hasta que termine la revisión."],
    provider_down: ["Servicio no disponible", "El proveedor no respondió. Conservamos tus datos. Intentá nuevamente cuando el servicio vuelva."],
    approved: ["Pago aprobado", "El servidor confirmó el pago."],
    rejected: ["Pago no aprobado", "Revisá el pedido e intentá nuevamente solo cuando la API lo permita."],
    refunded: ["Pago reembolsado", "El servidor confirmó la devolución del pago."],
    needs_attention: ["Necesitamos revisar el pedido", "El equipo debe verificar el pago o la entrega antes de continuar."],
  }[state];
  return <section className={`state-panel state-${state}`} aria-live="polite"><h2>{copy[0]}</h2><p>{copy[1]}</p></section>;
}

export function CheckoutFlow() {
  const cartContext = useCart();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<CheckoutUiState>("idle");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [identity, setIdentity] = useState<IdentityStatus | null>(null);
  const [consent, setConsent] = useState(false);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [billing, setBilling] = useState<BillingProfile[]>([]);
  const [settings, setSettings] = useState<StorefrontHome["settings"] | null>(null);
  const [addressId, setAddressId] = useState(0);
  const [billingId, setBillingId] = useState(0);
  const [method, setMethod] = useState<"shipping" | "pickup">("shipping");
  const [quote, setQuote] = useState<ShippingQuote | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const selectedAddress = addresses.find((item) => item.id === addressId);
  const selectedBilling = billing.find((item) => item.id === billingId);
  const pickupAvailable = Boolean(settings?.pickup_enabled && settings.pickup_label && settings.pickup_address);

  const recover = (cause: unknown, fallback: string, currentStep: number) => {
    if (cause instanceof ApiError) {
      const recovery = checkoutRecoveryFor(cause.code, currentStep);
      setStep(recovery.step); setState(recovery.state); setError(recovery.message);
    } else {
      setState("idle"); setError(cause instanceof Error ? cause.message : fallback);
    }
  };
  const loadAccount = async () => {
    setBusy(true); setError(""); setState("checking");
    try {
      const [me, identityStatus, addressRows, billingRows, home] = await Promise.all([
        apiRequest<Customer>("/customers/me/"), apiRequest<IdentityStatus>("/identity/status/"),
        apiRequest<Address[]>("/addresses/"), apiRequest<BillingProfile[]>("/billing-profiles/"),
        apiRequest<StorefrontHome>("/storefront/home/"),
      ]);
      setCustomer(me); setIdentity(identityStatus); setAddresses(addressRows); setBilling(billingRows); setSettings(home.settings);
      setAddressId(addressRows.find((item) => !item.needs_review)?.id ?? addressRows[0]?.id ?? 0);
      setBillingId(billingRows.find((item) => item.is_default)?.id ?? billingRows[0]?.id ?? 0);
      if (!home.settings.pickup_enabled) setMethod("shipping");
      if (!me.email_verified_at) throw new ApiError(422, "email_not_verified", "Email pendiente");
      if (!me.masked_dni || !me.profile.first_name || !me.profile.last_name || !me.profile.phone) throw new ApiError(422, "identity_missing", "Perfil incompleto");
      if (identityStatus.status === "approved") { setState("idle"); setStep(1); }
      else if (identityStatus.status === "pending_review") setState("pending_review");
      else if (identityStatus.status === "rejected") setState("rejected");
      else setState("idle");
    } catch (cause) { recover(cause, "Iniciá sesión y completá tu perfil para continuar.", 0); }
    finally { setBusy(false); }
  };
  const validateIdentity = async () => {
    if (!consent) { setError("Necesitamos tu consentimiento explícito para validar la identidad."); return; }
    setBusy(true); setError("");
    try {
      const result = await apiRequest<IdentityStatus>("/identity/validate/", { method: "POST", body: JSON.stringify({ consent: true }) });
      setIdentity(result);
      if (result.status === "approved") { setState("idle"); setStep(1); }
      else if (result.status === "rejected") setState("rejected");
      else setState("pending_review");
    } catch (cause) { recover(cause, "No pudimos validar la identidad.", 0); }
    finally { setBusy(false); }
  };
  const continueDelivery = () => {
    if (method === "shipping" && (!selectedAddress || selectedAddress.needs_review)) { setError("Elegí una dirección confirmada o confirmala antes de seguir."); return; }
    setError(""); setStep(2);
  };
  const getQuote = async () => {
    if (method === "pickup") { setQuote(null); setStep(3); return; }
    if (!addressId) return;
    setBusy(true); setError("");
    try { setQuote(await apiRequest<ShippingQuote>("/shipping/quote/", { method: "POST", body: JSON.stringify({ address_id: addressId }) })); setStep(3); }
    catch (cause) { recover(cause, "No pudimos cotizar el envío.", 2); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!cartContext?.cart?.lines.length) { recover(new ApiError(422, "empty_cart", "Carrito vacío"), "El carrito está vacío.", 3); return; }
    setBusy(true); setError("");
    try {
      const payload = { fulfillment_method: method, billing_profile_id: billingId, consent: true, idempotency_key: idempotencyKey.current, ...(method === "shipping" ? { address_id: addressId, shipping_quote_id: quote?.public_id } : {}) };
      const result = await apiRequest<CheckoutResponse>("/checkout/", { method: "POST", body: JSON.stringify(payload) });
      if (!result.checkout_url) { setState("pending_review"); return; }
      window.location.assign(result.checkout_url);
    } catch (cause) { recover(cause, "No pudimos iniciar el pago.", 3); }
    finally { setBusy(false); }
  };
  const steps = ["Cuenta e identidad", "Entrega", "Envío", "Revisión"];

  return <div className="checkout-layout">
    <ol className="checkout-stepper" aria-label="Progreso del checkout">{steps.map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined} className={index <= step ? "active" : ""}><span>{index + 1}</span>{label}</li>)}</ol>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {state !== "idle" && <CheckoutStatePanel state={state} />}
    {step === 0 && <section className="checkout-stage"><h2>Cuenta e identidad</h2>{customer ? <div className="review-block"><p><strong>{customer.profile.first_name} {customer.profile.last_name}</strong><br />{customer.email}<br />DNI {customer.masked_dni || "pendiente"}</p><Link href="/cuenta">Editar perfil</Link>{identity?.status !== "approved" && <><label className="check-label"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> Autorizo la validación de identidad para esta compra.</label><button className="button primary" disabled={busy} onClick={() => void validateIdentity()}>Validar identidad</button></>}</div> : <><p>Comprobamos email, perfil y DNI guardados antes de avanzar.</p><button className="button primary" disabled={busy} onClick={() => void loadAccount()}>{busy ? "Verificando…" : "Revisar cuenta"}</button></>}</section>}
    {step === 1 && <section className="checkout-stage"><h2>Elegí cómo recibir</h2><label><input type="radio" name="method" checked={method === "shipping"} onChange={() => setMethod("shipping")} /> Envío a domicilio</label>{pickupAvailable && <label><input type="radio" name="method" checked={method === "pickup"} onChange={() => setMethod("pickup")} /> {settings?.pickup_label}</label>}{method === "shipping" && <><label htmlFor="checkout-address">Dirección</label><select id="checkout-address" value={addressId} onChange={(event) => setAddressId(Number(event.target.value))}><option value={0}>Elegí una dirección</option>{addresses.map((address) => <option key={address.id} value={address.id}>{address.label}: {address.raw_address}{address.needs_review ? " · sin confirmar" : ""}</option>)}</select><Link href="/cuenta/direcciones">Agregar o confirmar dirección</Link></>}<div className="checkout-actions"><button className="button secondary" onClick={() => setStep(0)}>Atrás</button><button className="button primary" onClick={continueDelivery}>Continuar</button></div></section>}
    {step === 2 && <section className="checkout-stage"><h2>{method === "pickup" ? settings?.pickup_label : "Cotizá el envío"}</h2><p>{method === "pickup" ? <>{settings?.pickup_address}<br />{settings?.pickup_hours}</> : `Dirección: ${selectedAddress?.raw_address ?? "sin elegir"}`}</p><div className="checkout-actions"><button className="button secondary" onClick={() => setStep(1)}>Editar entrega</button><button className="button primary" disabled={busy} onClick={() => void getQuote()}>{busy ? "Consultando…" : method === "pickup" ? "Continuar" : "Cotizar envío"}</button></div></section>}
    {step === 3 && <section className="checkout-stage"><h2>Revisá antes de pagar</h2><div className="checkout-review"><section><h3>Productos</h3>{cartContext?.cart?.lines.map((line) => <p key={line.id}>{line.name || line.sku} · {line.quantity} <strong>{formatMoney(line.line_total)}</strong></p>)}{cartContext?.cart && <p className="review-total">Total del carrito <strong>{formatMoney(cartContext.cart.total)}</strong></p>}<Link href="/carrito">Editar carrito</Link></section><section><h3>Entrega</h3><p>{method === "pickup" ? <><strong>{settings?.pickup_label}</strong><br />{settings?.pickup_address}<br />{settings?.pickup_hours}</> : selectedAddress?.raw_address}</p>{quote && <p>Envío {formatMoney(quote.total_amount)} · vence {new Date(quote.expires_at).toLocaleString("es-AR")}</p>}<button className="text-button" onClick={() => setStep(1)}>Editar entrega</button></section><section><h3>Datos fiscales</h3><label htmlFor="billing">Perfil fiscal</label><select id="billing" value={billingId} onChange={(event) => setBillingId(Number(event.target.value))}><option value={0}>Elegí un perfil</option>{billing.map((profile) => <option key={profile.id} value={profile.id}>{profile.label} · {profile.masked_cuit}</option>)}</select>{selectedBilling && <p>{selectedBilling.legal_name}</p>}<Link href="/cuenta/fiscal">Administrar perfiles</Link></section></div><p>Mercado Pago abrirá en su sitio. Solo el estado del servidor confirma el pago.</p><div className="checkout-actions"><button className="button secondary" onClick={() => setStep(2)}>Atrás</button><button className="button primary" disabled={!billingId || busy || !cartContext?.cart?.lines.length} onClick={() => void confirm()}>{busy ? "Confirmando…" : "Ir a Mercado Pago"}</button></div></section>}
  </div>;
}
