"use client";

import { CheckCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRef, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import { checkoutRecoveryFor } from "@/lib/checkout-recovery";
import { formatMoney } from "@/lib/format";
import { useCart } from "@/components/cart/cart-provider";
import { ActiveCheckoutCard } from "@/components/cart/active-checkout-card";
import { ShippingOptionSelector } from "@/components/checkout/shipping-option-selector";
import type { Address, BillingProfile, CheckoutResponse, Customer, IdentityStatus, ShippingQuote, ShippingQuoteOptions, StorefrontHome } from "@/lib/types";

export type CheckoutUiState = "idle" | "checking" | "pending_review" | "shipping_pending" | "provider_down" | "approved" | "rejected" | "refunded" | "needs_attention";

export function getTrustedOrderState(_params: URLSearchParams, serverPaymentStatus: string | null): CheckoutUiState {
  if (!serverPaymentStatus || ["not_started", "pending"].includes(serverPaymentStatus)) return "checking";
  if (serverPaymentStatus === "paid") return "approved";
  if (serverPaymentStatus === "failed") return "rejected";
  if (serverPaymentStatus === "refunded") return "refunded";
  if (serverPaymentStatus === "needs_attention") return "needs_attention";
  return "checking";
}

export function CheckoutStatePanel({ state, orderId = "" }: { state: CheckoutUiState; orderId?: string }) {
  const copy = {
    idle: ["Listo para continuar", "Revisá los datos antes de confirmar."],
    checking: ["Estamos revisando tu pedido", "Puede demorar unos segundos."],
    pending_review: ["Estamos verificando tus datos", "Te avisaremos cuando puedas continuar con el pago."],
    shipping_pending: ["Estamos coordinando el envío", "Te avisaremos el costo y podrás pagar todo junto desde tu pedido."],
    provider_down: ["Servicio no disponible", "Guardamos tus datos. Intentá nuevamente en unos minutos."],
    approved: ["Pago aprobado", "Tu compra quedó confirmada."],
    rejected: ["No pudimos aprobar el pago", "Volvé al pedido para intentarlo nuevamente."],
    refunded: ["Reembolso realizado", "El importe fue devuelto por el mismo medio de pago."],
    needs_attention: ["Estamos revisando tu pedido", "Te avisaremos cuando tengamos novedades."],
  }[state];
  return <section className={`state-panel state-${state}`} aria-live="polite"><h2>{copy[0]}</h2><p>{copy[1]}</p>{orderId && <Link className="button primary" href={`/pedidos/${orderId}`}>Ver pedido y seguir el estado</Link>}</section>;
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
  const [quotes, setQuotes] = useState<ShippingQuote[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [quoteErrors, setQuoteErrors] = useState<string[]>([]);
  const [pendingOrderId, setPendingOrderId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const selectedAddress = addresses.find((item) => item.id === addressId);
  const selectedBilling = billing.find((item) => item.id === billingId);
  const quote = quotes.find((item) => item.public_id === selectedQuoteId) ?? null;
  const pickupAvailable = Boolean(settings?.pickup_enabled);
  const pickupLabel = settings?.pickup_label?.trim() || "Retiro en tienda";
  const pickupAddress = settings?.pickup_address?.trim() || "El punto de retiro se coordinará con la tienda.";
  const pickupHours = settings?.pickup_hours?.trim() || "El horario se confirmará con tu pedido.";
  const profileComplete = Boolean(
    customer?.email_verified_at
    && customer.masked_dni
    && customer.profile.first_name
    && customer.profile.last_name
    && customer.profile.phone,
  );
  const identityComplete = Boolean(
    identity?.required === false
    || identity?.status === "not_required"
    || identity?.status === "approved",
  );
  const dataComplete = profileComplete && identityComplete;

  if (cartContext?.cart?.active_checkout) {
    return <div className="checkout-resume"><ActiveCheckoutCard checkout={cartContext.cart.active_checkout} /><Link className="text-button" href="/carrito">Modificar productos</Link></div>;
  }

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
      if (identityStatus.required === false || identityStatus.status === "not_required") setState("idle");
      else if (identityStatus.status === "approved") setState("idle");
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
      if (result.required === false || result.status === "not_required") setState("idle");
      else if (result.status === "approved") setState("idle");
      else if (result.status === "rejected") setState("rejected");
      else setState("pending_review");
    } catch (cause) { recover(cause, "No pudimos validar la identidad.", 0); }
    finally { setBusy(false); }
  };
  const continueDelivery = () => {
    if (method === "shipping" && (!selectedAddress || selectedAddress.needs_review)) { setError("Elegí una dirección confirmada o confirmala antes de seguir."); return; }
    setError(""); setStep(2);
  };
  const continueFromData = () => {
    if (!dataComplete) {
      setError("Completá y validá tus datos antes de continuar.");
      return;
    }
    setError("");
    setStep(1);
  };
  const getQuote = async () => {
    if (method === "pickup") { setQuotes([]); setSelectedQuoteId(""); setStep(3); return; }
    if (!addressId) return;
    setBusy(true); setError("");
    try {
      const options = await apiRequest<ShippingQuoteOptions>("/shipping/quotes/", { method: "POST", body: JSON.stringify({ address_id: addressId }) });
      const ordered = [...options.results].sort((left, right) => {
        if (left.amount_pending) return 1;
        if (right.amount_pending) return -1;
        return Number(left.total_amount) - Number(right.total_amount);
      });
      setQuotes(ordered);
      setSelectedQuoteId(ordered[0]?.public_id ?? "");
      setQuoteErrors(options.errors.map((item) => `${item.label} no está disponible en este momento.`));
      setStep(3);
    }
    catch (cause) { recover(cause, "No pudimos cotizar el envío.", 2); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!cartContext?.cart?.lines.length) { recover(new ApiError(422, "empty_cart", "Carrito vacío"), "El carrito está vacío.", 3); return; }
    setBusy(true); setError("");
    try {
      const payload = { fulfillment_method: method, billing_profile_id: billingId, consent: identity?.required !== false, idempotency_key: idempotencyKey.current, ...(method === "shipping" ? { address_id: addressId, shipping_quote_id: quote?.public_id } : {}) };
      const result = await apiRequest<CheckoutResponse>("/checkout/", { method: "POST", body: JSON.stringify(payload) });
      if (!result.checkout_url) {
        setPendingOrderId(String(result.order_id));
        setState(result.shipping_cost_status === "pending_agreement" ? "shipping_pending" : "pending_review");
        return;
      }
      window.location.assign(result.checkout_url);
    } catch (cause) { recover(cause, "No pudimos iniciar el pago.", 3); }
    finally { setBusy(false); }
  };
  const steps = ["Tus datos", "Entrega", "Opciones", "Revisión"];

  return <div className="checkout-layout">
    <ol className="checkout-stepper" aria-label="Progreso del checkout">{steps.map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined} className={index <= step ? "active" : ""}><span>{index + 1}</span>{label}</li>)}</ol>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {step === 3 && quoteErrors.map((message) => <p className="management-notice" key={message}>{message}</p>)}
    {state !== "idle" && <CheckoutStatePanel orderId={pendingOrderId} state={state} />}
    {!pendingOrderId && step === 0 && <section className="checkout-stage"><h2>Tus datos</h2>{customer ? <div className="review-block">{dataComplete && <p className="identity-review-status" role="status"><CheckCircle aria-hidden="true" size={24} weight="fill" />Datos completos</p>}<p><strong>{customer.profile.first_name} {customer.profile.last_name}</strong><br />{customer.email}<br />DNI {customer.masked_dni || "pendiente"}</p><Link href="/cuenta">Editar perfil</Link>{identity?.required !== false && identity?.status !== "not_required" && identity?.status !== "approved" && <><label className="check-label"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> Autorizo la verificación de mis datos para esta compra.</label><button className="button primary" disabled={busy} onClick={() => void validateIdentity()}>Verificar mis datos</button></>}{dataComplete && <button className="button primary" type="button" onClick={continueFromData}>Continuar a entrega</button>}</div> : <><p>Antes de continuar, revisá que tus datos estén completos.</p><button className="button primary" disabled={busy} type="button" onClick={() => void loadAccount()}>{busy ? "Verificando…" : "Revisar mis datos"}</button></>}</section>}
    {!pendingOrderId && step === 1 && <section className="checkout-stage"><h2>Elegí cómo recibir</h2><label><input type="radio" name="method" checked={method === "shipping"} onChange={() => setMethod("shipping")} /> Envío a domicilio</label>{pickupAvailable && <label><input type="radio" name="method" checked={method === "pickup"} onChange={() => setMethod("pickup")} /> {pickupLabel}</label>}{method === "shipping" && <><label htmlFor="checkout-address">Dirección</label><select id="checkout-address" value={addressId} onChange={(event) => setAddressId(Number(event.target.value))}><option value={0}>Elegí una dirección</option>{addresses.map((address) => <option key={address.id} value={address.id}>{address.label}: {address.raw_address}{address.needs_review ? " · sin confirmar" : ""}</option>)}</select><Link href="/cuenta/direcciones">Agregar o confirmar dirección</Link></>}<div className="checkout-actions"><button className="button secondary" onClick={() => setStep(0)}>Atrás</button><button className="button primary" onClick={continueDelivery}>Continuar</button></div></section>}
    {!pendingOrderId && step === 2 && <section className="checkout-stage"><h2>{method === "pickup" ? pickupLabel : "Cotizá el envío"}</h2><p>{method === "pickup" ? <>{pickupAddress}<br />{pickupHours}</> : `Dirección: ${selectedAddress?.raw_address ?? "sin elegir"}`}</p><div className="checkout-actions"><button className="button secondary" onClick={() => setStep(1)}>Editar entrega</button><button className="button primary" disabled={busy} onClick={() => void getQuote()}>{busy ? "Consultando…" : method === "pickup" ? "Continuar" : "Cotizar envío"}</button></div></section>}
    {!pendingOrderId && step === 3 && <section className="checkout-stage"><h2>Revisá antes de confirmar</h2>{method === "shipping" && <ShippingOptionSelector options={quotes} selectedId={selectedQuoteId} onSelect={setSelectedQuoteId} />}<div className="checkout-review"><section><h3>Productos</h3>{cartContext?.cart?.lines.map((line) => <p key={line.id}>{line.product_name}{line.variant_name ? ` · ${line.variant_name}` : ""} · {line.quantity} <strong>{formatMoney(line.line_total)}</strong></p>)}{cartContext?.cart && <p className="review-total">Total del carrito <strong>{formatMoney(cartContext.cart.total)}</strong></p>}<Link href="/carrito">Editar carrito</Link></section><section><h3>Entrega</h3><p>{method === "pickup" ? <><strong>{pickupLabel}</strong><br />{pickupAddress}<br />{pickupHours}</> : selectedAddress?.raw_address}</p>{quote && <p>{quote.amount_pending ? "Costo de envío a confirmar" : <>Envío {formatMoney(quote.total_amount)} · válido hasta {new Date(quote.expires_at).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}</>}</p>}<button className="text-button" onClick={() => setStep(1)}>Editar entrega</button></section><section><h3>Datos fiscales</h3><label htmlFor="billing">Perfil fiscal</label><select id="billing" value={billingId} onChange={(event) => setBillingId(Number(event.target.value))}><option value={0}>Elegí un perfil</option>{billing.map((profile) => <option key={profile.id} value={profile.id}>{profile.label} · {profile.masked_cuit}</option>)}</select>{selectedBilling && <p>{selectedBilling.legal_name}</p>}<Link href="/cuenta/fiscal">Administrar perfiles</Link></section></div><p>{quote?.amount_pending ? "Crearemos el pedido y te avisaremos cuando el costo esté listo para pagar todo junto." : "Te vamos a llevar a Mercado Pago para completar el pago."}</p><div className="checkout-actions"><button className="button secondary" onClick={() => setStep(2)}>Atrás</button><button className="button primary" disabled={!billingId || busy || !cartContext?.cart?.lines.length || (method === "shipping" && !quote)} onClick={() => void confirm()}>{busy ? "Confirmando…" : quote?.amount_pending ? "Solicitar coordinación" : "Ir a Mercado Pago"}</button></div></section>}
  </div>;
}
