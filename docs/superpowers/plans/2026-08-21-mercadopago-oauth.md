# Mercado Pago OAuth de un clic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que el propietario conecte la única cuenta de Mercado Pago desde Administración mediante una autorización oficial de un clic, sin copiar Access Tokens.

**Architecture:** Django inicia Authorization Code con PKCE S256 y guarda el intento efímero, de un solo uso, en caché. El callback público canjea el código, cifra access/refresh token dentro de la configuración existente, deriva el collector y redirige al panel; el checkout renueva el token bajo demanda antes de vencer. Next.js muestra un panel específico de conexión, reconexión y desconexión sin exponer secretos.

**Tech Stack:** Django 5.2, DRF, Redis cache, PostgreSQL, Next.js 16, React 19, TypeScript, Vitest y Playwright.

**Spec:** `PRODUCT.md` y documentación oficial de OAuth de Mercado Pago.

## Global Constraints

- El operador no copia access tokens, refresh tokens ni collector IDs.
- Client ID, Client Secret y secreto de webhook son secretos de despliegue, nunca campos visibles del panel.
- OAuth usa `state` aleatorio de un solo uso, expiración de 10 minutos y PKCE S256.
- El redirect URI es estático y HTTPS en producción.
- Los tokens quedan cifrados con `CONFIG_ENCRYPTION_MASTER_KEY` y nunca aparecen en API, logs ni URL.
- El flujo sigue siendo B2C de un solo comercio; no se incorporan comisiones ni marketplace.

---

### Task 1: Contrato OAuth y persistencia cifrada

**Files:**
- Create: `backend/commerce/mercadopago_oauth.py`
- Modify: `backend/backoffice/integrations.py`
- Modify: `backend/commerce/provider_config.py`
- Test: `backend/tests/test_mercadopago_oauth.py`

**Interfaces:**
- Consumes: `IntegrationConfiguration`, `seal_secret_map`, `unseal_secret_map`, Django cache y settings OAuth.
- Produces: `create_authorization_session(user_id) -> str`, `consume_authorization_callback(code, state, actor) -> IntegrationConfiguration`, `disconnect_mercadopago(actor)`, `resolved_mercadopago_access_token() -> str`.

- [x] **Step 1: Write failing tests for PKCE, one-use state, encrypted token storage, safe serialization, refresh and disconnect.**
- [x] **Step 2: Run `pytest -q tests/test_mercadopago_oauth.py` and confirm failures are caused by the missing module/contracts.**
- [x] **Step 3: Implement the OAuth service with injectable token transport, strict response validation, encrypted storage and on-demand refresh.**
- [x] **Step 4: Route `get_payment_adapter()` through the valid OAuth token while retaining the existing environment fallback.**
- [x] **Step 5: Run the focused backend suite and commit the service boundary.**

### Task 2: API de conectar, callback y desconectar

**Files:**
- Create: `backend/backoffice/oauth_views.py`
- Modify: `backend/backoffice/urls.py`
- Modify: `backend/api_urls.py`
- Modify: `backend/backoffice/serializers.py`
- Test: `backend/tests/test_mercadopago_oauth_api.py`

**Interfaces:**
- Consumes: Task 1 service functions.
- Produces: `POST /api/v1/management/integrations/mercadopago/oauth/start/`, `GET /api/v1/payments/mercadopago/oauth/callback/`, `POST /api/v1/management/integrations/mercadopago/oauth/disconnect/`.

- [x] **Step 1: Write failing API tests for owner permissions, authorization URL, rejected/replayed state, callback redirects, audit events and disconnect.**
- [x] **Step 2: Run the API tests and confirm the endpoints are absent.**
- [x] **Step 3: Implement typed DRF views; the callback is public but accepts only a live server-side state.**
- [x] **Step 4: Publish exact OpenAPI response/error contracts without exposing secrets.**
- [x] **Step 5: Run focused API/OpenAPI tests and commit.**

### Task 3: Panel de conexión de un clic

**Files:**
- Create: `frontend/components/management/mercadopago-connect-panel.tsx`
- Modify: `frontend/components/management/integration-panel.tsx`
- Modify: `frontend/lib/management/types.ts`
- Modify: `frontend/app/styles.css`
- Test: `frontend/tests/management-mercadopago-oauth.test.tsx`
- Test: `frontend/tests/mock-api.mjs`

**Interfaces:**
- Consumes: OAuth status and start/disconnect APIs from Task 2.
- Produces: operator UI with `Conectar Mercado Pago`, `Reconectar` and guarded `Desconectar` actions.

- [x] **Step 1: Write failing component tests for ready, connected, reconnect-required, not-ready and callback-result states.**
- [x] **Step 2: Confirm RED because the specialized panel does not exist.**
- [x] **Step 3: Implement the panel; `Conectar` requests the URL then performs `window.location.assign`, and callback query state refreshes the server data.**
- [x] **Step 4: Keep technical setup text out of the normal connected state and provide a concise operator recovery message on errors.**
- [x] **Step 5: Run Vitest and the focused Playwright management journey; commit.**

### Task 4: Configuración operativa y cierre

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Modify: `compose.yaml`
- Modify: `compose.prod.yaml`
- Modify: `PRODUCT.md`
- Modify: `docs/operations/donweb-production.md`

**Interfaces:**
- Consumes: static callback path from Task 2.
- Produces: `MERCADOPAGO_OAUTH_CLIENT_ID`, `MERCADOPAGO_OAUTH_CLIENT_SECRET`, `MERCADOPAGO_OAUTH_REDIRECT_URI` and documented Mercado Pago application setup.

- [x] **Step 1: Add fail-closed settings tests for partial OAuth configuration and non-HTTPS production redirect URI.**
- [x] **Step 2: Add environment/Compose wiring without placing live values in the repository.**
- [x] **Step 3: Document the one-time Mercado Pago application setup and the exact static callback URL.**
- [x] **Step 4: Run full backend/frontend tests, OpenAPI validation, production builds and Compose config validation.**
- [x] **Step 5: Audit the diff for secrets, run `git diff --check`, commit and leave the local storefront running.**

## Self-review

- Spec coverage: connect, callback, encrypted credentials, refresh, reconnect, disconnect, audit, UI and Donweb configuration all map to a task.
- Placeholder scan: no deferred implementation or live credential is required in source.
- Type consistency: backend response fields feed the specialized frontend panel; endpoints and status vocabulary are fixed in Tasks 2 and 3.

## Evidencia final

- Backend completo: 296 aprobadas, 53 omitidas por entorno.
- Contrato OAuth: 8 aprobadas; integración histórica + OAuth: 14 aprobadas.
- Frontend: 99 pruebas unitarias aprobadas; Playwright OAuth 4/4 en 360, 768, 1024 y 1440 px.
- Ruff, Django check, migraciones, OpenAPI, Compose local/producción, TypeScript, ESLint y build Next.js: aprobados.
