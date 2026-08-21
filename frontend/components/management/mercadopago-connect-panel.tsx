"use client";

import { useState } from "react";

import type { IntegrationConfiguration } from "@/lib/management/types";


type AuthorizationStart = {
  authorization_url: string;
  callback_url: string;
};


function defaultNavigate(url: string) {
  window.location.assign(url);
}


export function MercadoPagoConnectPanel({
  integration,
  onConnect,
  onDisconnect,
  navigate = defaultNavigate,
  result,
}: {
  integration: IntegrationConfiguration;
  onConnect: () => Promise<AuthorizationStart>;
  onDisconnect: () => Promise<IntegrationConfiguration>;
  navigate?: (url: string) => void;
  result?: string;
}) {
  const [current, setCurrent] = useState(integration);
  const [state, setState] = useState<"idle" | "connecting" | "disconnecting" | "error">(
    "idle",
  );
  const oauthStatus = current.oauth_status ?? "disconnected";
  const connected = oauthStatus === "connected";
  const reconnect = oauthStatus === "reconnect_required";
  const ready = Boolean(current.oauth_ready);

  const connect = async () => {
    setState("connecting");
    try {
      const authorization = await onConnect();
      navigate(authorization.authorization_url);
    } catch {
      setState("error");
    }
  };

  const disconnect = async () => {
    setState("disconnecting");
    try {
      setCurrent(await onDisconnect());
      setState("idle");
    } catch {
      setState("error");
    }
  };

  return (
    <div className="mercadopago-connect-layout">
      {result === "connected" && (
        <p className="success-message" role="status">Mercado Pago quedó conectado.</p>
      )}
      {result === "cancelled" && (
        <p className="management-notice" role="status">La conexión fue cancelada. No hicimos cambios.</p>
      )}
      {result === "error" && (
        <p className="inline-error" role="alert">No pudimos completar la conexión. Intentá nuevamente.</p>
      )}

      <section className="management-form-section mercadopago-connect-card">
        <div className="mercadopago-mark" aria-hidden="true">mp</div>
        <div className="mercadopago-connect-copy">
          <p className="management-kicker">Cobros online</p>
          <h2>{connected ? "Cuenta conectada" : reconnect ? "Volvé a conectar tu cuenta" : "Conectá Mercado Pago"}</h2>
          {connected ? (
            <p>
              Tu tienda ya puede crear cobros con Checkout Pro.
              {current.connected_account_id ? ` Cuenta ${current.connected_account_id}.` : ""}
            </p>
          ) : reconnect ? (
            <p>La autorización venció. Conectala otra vez para seguir cobrando.</p>
          ) : (
            <p>Ingresá en Mercado Pago, revisá los permisos y confirmá. No necesitás copiar claves.</p>
          )}
        </div>
        <div className="mercadopago-connect-actions">
          {!connected && (
            <button
              className="button primary"
              disabled={!ready || state === "connecting"}
              onClick={() => void connect()}
              type="button"
            >
              {state === "connecting"
                ? "Abriendo Mercado Pago…"
                : reconnect
                  ? "Volver a conectar"
                  : "Conectar Mercado Pago"}
            </button>
          )}
          {connected && (
            <button
              className="button secondary"
              disabled={state === "disconnecting"}
              onClick={() => void disconnect()}
              type="button"
            >
              {state === "disconnecting" ? "Desconectando…" : "Desconectar"}
            </button>
          )}
        </div>
      </section>

      {!ready && !connected && (
        <p className="management-notice" role="status">
          Falta habilitar la conexión segura de Mercado Pago en el servidor.
        </p>
      )}
      {state === "error" && (
        <p className="inline-error" role="alert">No pudimos completar la acción. Intentá nuevamente.</p>
      )}
      <section className="management-form-section mercadopago-connect-help">
        <h2>Cómo funciona</h2>
        <ol>
          <li>Presioná conectar.</li>
          <li>Confirmá la autorización en Mercado Pago.</li>
          <li>Volvés automáticamente con la cuenta lista.</li>
        </ol>
      </section>
    </div>
  );
}
