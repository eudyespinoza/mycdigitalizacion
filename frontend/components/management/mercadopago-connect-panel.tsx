"use client";

import { type FormEvent, useState } from "react";

import type { IntegrationConfiguration, IntegrationUpdate } from "@/lib/management/types";

type PanelState =
  | "idle"
  | "saving"
  | "connecting"
  | "disconnecting"
  | "error";


export function MercadoPagoConnectPanel({
  integration,
  onSave,
  onConnect,
  onDisconnect,
  result,
}: {
  integration: IntegrationConfiguration;
  onSave: (payload: IntegrationUpdate) => Promise<IntegrationConfiguration>;
  onConnect: () => Promise<IntegrationConfiguration>;
  onDisconnect: () => Promise<IntegrationConfiguration>;
  result?: string;
}) {
  const [current, setCurrent] = useState(integration);
  const [state, setState] = useState<PanelState>("idle");
  const [environment, setEnvironment] = useState(
    integration.version === 0 ? "production" : integration.environment,
  );
  const [clientId, setClientId] = useState(
    String(integration.public_config.oauth_client_id ?? ""),
  );
  const [clientSecret, setClientSecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const oauthStatus = current.oauth_status ?? "disconnected";
  const connected = oauthStatus === "connected";
  const reconnect = oauthStatus === "reconnect_required";
  const ready = Boolean(current.oauth_ready);
  const webhookReady = Boolean(current.webhook_ready);
  const connectedBrandName = String(
    current.public_config.connected_brand_name ?? "",
  );

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    try {
      const updated = await onSave({
        environment,
        public_config: { oauth_client_id: clientId.trim() },
        secrets: {
          oauth_client_secret: clientSecret,
          webhook_secret: webhookSecret,
        },
      });
      setCurrent(updated);
      setClientSecret("");
      setWebhookSecret("");
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const connect = async () => {
    setState("connecting");
    try {
      setCurrent(await onConnect());
      setState("idle");
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
              {webhookReady
                ? "La cuenta y las notificaciones de pago están preparadas."
                : "La cuenta está conectada; todavía falta configurar la firma del webhook."}
              {current.connected_account_id ? ` Cuenta ${current.connected_account_id}.` : ""}
              {connectedBrandName
                ? ` El checkout muestra “${connectedBrandName}”.`
                : ""}
            </p>
          ) : reconnect ? (
            <p>La autorización venció. Conectala otra vez para seguir cobrando.</p>
          ) : (
            <p>Guardá los datos de la aplicación y validá la cuenta propia de la tienda en un solo paso.</p>
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
                ? "Conectando…"
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

      {connected && connectedBrandName && (
        <p className="management-notice" role="status">
          Mercado Pago identifica esta cuenta como “{connectedBrandName}”. Ese nombre
          pertenece al perfil comercial de Mercado Pago y se cambia desde esa cuenta.
          El nombre público de la tienda ya se usa en el detalle del cargo de tarjeta.
        </p>
      )}

      <form className="management-form-section mercadopago-configuration-card" onSubmit={save}>
        <div className="management-section-heading">
          <div>
            <h2>Configuración de la aplicación</h2>
            <p>Estos datos identifican a tu aplicación. Las claves se guardan cifradas y no vuelven a mostrarse.</p>
          </div>
        </div>
        <div className="management-field-grid">
          <label>
            Ambiente
            <select
              onChange={(event) => setEnvironment(event.target.value as typeof environment)}
              value={environment}
            >
              <option value="sandbox">Pruebas</option>
              <option value="qa">QA</option>
              <option value="production">Producción</option>
            </select>
          </label>
          <label>
            ID de aplicación (Client ID)
            <input
              autoComplete="off"
              onChange={(event) => setClientId(event.target.value)}
              required
              value={clientId}
            />
          </label>
          <label>
            Client Secret
            {current.secret_fields.oauth_client_secret && <small className="secret-configured">Configurado</small>}
            <input
              autoComplete="new-password"
              onChange={(event) => setClientSecret(event.target.value)}
              placeholder={current.secret_fields.oauth_client_secret ? "Dejá vacío para conservarlo" : "Ingresá el secreto"}
              type="password"
              value={clientSecret}
            />
          </label>
          <label>
            Clave secreta del webhook
            {current.secret_fields.webhook_secret && <small className="secret-configured">Configurada</small>}
            <input
              autoComplete="new-password"
              onChange={(event) => setWebhookSecret(event.target.value)}
              placeholder={current.secret_fields.webhook_secret ? "Dejá vacío para conservarla" : "Ingresala desde Webhooks"}
              type="password"
              value={webhookSecret}
            />
          </label>
        </div>
        <div className="management-form-actions">
          <button className="button primary" disabled={state === "saving"} type="submit">
            {state === "saving" ? "Guardando…" : "Guardar configuración"}
          </button>
        </div>
      </form>

      {!ready && !connected && (
        <p className="management-notice" role="status">
          Falta habilitar la conexión segura: cargá el Client ID y el Client Secret de tu aplicación.
        </p>
      )}
      {ready && !webhookReady && (
        <p className="management-notice" role="status">
          Falta configurar la firma del webhook. Podés conectar la cuenta, pero el checkout productivo seguirá deshabilitado hasta completarla.
        </p>
      )}
      {current.last_test_message && (
        <p className={current.last_test_status === "success" ? "success-message" : "management-notice"} role="status">
          {current.last_test_message}
        </p>
      )}
      {state === "error" && (
        <p className="inline-error" role="alert">No pudimos completar la acción. Revisá los datos e intentá nuevamente.</p>
      )}
      <section className="management-form-section mercadopago-connect-help">
        <h2>Cómo conectarlo</h2>
        <ol>
          <li>Creá la aplicación en Mercado Pago y copiá el Client ID y el Client Secret.</li>
          <li>Guardá y presioná “Conectar Mercado Pago”; verificaremos directamente la cuenta propia.</li>
          <li>Copiá la clave secreta de Webhooks para habilitar los cobros productivos.</li>
        </ol>
      </section>
    </div>
  );
}
