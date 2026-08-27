# ARCA A13 Fiscal Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure ARCA Padrón A13 configuration and automatically resolve/validate DNI or CUIT when a customer saves a fiscal profile, while keeping checkout usable when ARCA is not configured.

**Architecture:** A dedicated `ArcaA13Client` owns certificate loading, WSAA ticket creation/caching and SOAP calls; a fiscal-identity service applies the 11-digit direct lookup and 7/8-digit DNI resolution rules. Existing encrypted integration configuration stores credentials, the billing serializer persists only the final CUIT, and the frontend exposes file-based configuration plus clear checkout/fiscal-profile states.

**Tech Stack:** Django 5, Django REST Framework, `cryptography`, Python XML/HTTP utilities, Next.js 15, React 19, TypeScript, Vitest, Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-arca-a13-fiscal-identity-design.md`

## Global Constraints

- Use ARCA service identifier `ws_sr_padron_a13`.
- Eleven normalized digits must call `getPersona` directly and never call `getIdPersonaListByDocumento`.
- Seven or eight normalized digits must call `getIdPersonaListByDocumento` and then `getPersona` with the resolved CUIT.
- When the integration is absent, disabled, or incomplete, allow a checksum-valid full CUIT without remote validation and require DNI users to enter their full CUIT.
- ARCA credentials remain write-only, encrypted through `IntegrationConfiguration.sealed_secrets`, and never appear in API responses, logs, audit payloads, or errors.
- ARCA validation does not replace the independent RENAPER identity-validation rule.
- Do not add a schema migration unless implementation reveals a data requirement that cannot be represented by the existing integration and billing-profile models.

---

### Task 1: Checkout fiscal recovery links and layout

**Files:**
- Modify: `frontend/tests/identity-checkout-bypass.test.tsx`
- Modify: `frontend/components/checkout/checkout-flow.tsx`
- Modify: `frontend/app/styles.css`

**Interfaces:**
- Consumes: existing `CheckoutFlow` account loading and `error` state.
- Produces: an alert containing links named `Completar datos personales` (`/cuenta`) and `Cargar datos fiscales` (`/cuenta/fiscal`) when step 1 cannot continue because account data is incomplete.

- [ ] **Step 1: Complete the failing UI test**

Add assertions to the existing `checkout links to fiscal data when identity data blocks the first step` test:

```tsx
expect(screen.getByRole("link", { name: "Completar datos personales" })).toHaveAttribute("href", "/cuenta");
expect(screen.getByRole("link", { name: "Cargar datos fiscales" })).toHaveAttribute("href", "/cuenta/fiscal");
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && pnpm exec vitest run tests/identity-checkout-bypass.test.tsx`

Expected: FAIL because the links are not rendered.

- [ ] **Step 3: Render contextual recovery actions and pin checkout content to the right column**

Replace the plain checkout error paragraph with a structured alert whose actions are shown at step zero, then add CSS selectors for `.checkout-error`, `.checkout-error-actions`, and explicit `grid-column: 2` placement for the alert/stage. Override those selectors to column 1 inside the existing mobile breakpoint.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && pnpm exec vitest run tests/identity-checkout-bypass.test.tsx`

Expected: both checkout identity tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/identity-checkout-bypass.test.tsx frontend/components/checkout/checkout-flow.tsx frontend/app/styles.css
git commit -m "fix: link checkout identity errors to account data"
```

### Task 2: ARCA integration definition, encrypted credentials, and file inputs

**Files:**
- Modify: `backend/tests/test_backoffice_integrations.py`
- Modify: `backend/backoffice/integrations.py`
- Modify: `frontend/tests/management-integrations.test.tsx`
- Modify: `frontend/lib/management/types.ts`
- Modify: `frontend/lib/management/integration-fields.ts`
- Modify: `frontend/components/management/integration-editor.tsx`

**Interfaces:**
- Consumes: `IntegrationConfiguration.public_config`, encrypted `sealed_secrets`, and the generic management integration endpoints.
- Produces: provider key `arca_a13`; public keys `represented_cuit`, `environment`, `wsaa_url`, `a13_url`; secret keys `certificate_pem`, `private_key_pem`, `private_key_passphrase`, `pfx_base64`, `pfx_password`; frontend `IntegrationField` file metadata.

- [ ] **Step 1: Write failing backend configuration tests**

Assert that the provider list exposes `arca_a13`, that a valid represented CUIT plus certificate/key or PFX marks the enabled provider ready, that an invalid/incomplete bundle remains incomplete, and that PATCH responses/audit entries expose only configured flags and secret names.

- [ ] **Step 2: Verify backend RED**

Run: `cd backend && pytest tests/test_backoffice_integrations.py -q`

Expected: FAIL because `arca_a13` is absent.

- [ ] **Step 3: Add the ARCA definition and bundle-aware readiness**

Define the provider label `Identidad fiscal ARCA · Padrón A13`, whitelist its fields, and special-case readiness as:

```python
has_pem = bool(secrets.get("certificate_pem") and secrets.get("private_key_pem"))
has_pfx = bool(secrets.get("pfx_base64"))
ready = enabled and valid_represented_cuit and (has_pem or has_pfx) and environment in {"testing", "production"}
```

Keep all credential values inside `sealed_secrets`.

- [ ] **Step 4: Verify backend GREEN**

Run: `cd backend && pytest tests/test_backoffice_integrations.py -q`

Expected: PASS.

- [ ] **Step 5: Write failing frontend file-input tests**

Render the ARCA integration editor, upload a PEM certificate/key and a binary PFX, submit, and assert that the management PATCH receives PEM text or base64 PFX while omitted files remain empty so the backend preserves existing secrets.

- [ ] **Step 6: Verify frontend RED**

Run: `cd frontend && pnpm exec vitest run tests/management-integrations.test.tsx`

Expected: FAIL because `arca_a13` and file fields are not supported.

- [ ] **Step 7: Implement ARCA fields and asynchronous file serialization**

Extend `IntegrationProvider` with `arca_a13`, extend `IntegrationField.type` with `file`, and add `accept` plus `encoding: "text" | "base64"`. In `IntegrationEditor`, serialize PEM via `File.text()` and PFX via `File.arrayBuffer()` to base64 before calling `onSave`.

- [ ] **Step 8: Verify frontend GREEN**

Run: `cd frontend && pnpm exec vitest run tests/management-integrations.test.tsx`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/backoffice/integrations.py backend/tests/test_backoffice_integrations.py frontend/lib/management/types.ts frontend/lib/management/integration-fields.ts frontend/components/management/integration-editor.tsx frontend/tests/management-integrations.test.tsx
git commit -m "feat: configure ARCA A13 credentials securely"
```

### Task 3: WSAA authentication and A13 SOAP adapter

**Files:**
- Create: `backend/accounts/arca_a13.py`
- Create: `backend/tests/test_arca_a13_client.py`

**Interfaces:**
- Consumes: `ArcaA13Settings(environment, represented_cuit, certificate_pem, private_key_pem, private_key_passphrase, pfx_base64, pfx_password, wsaa_url, a13_url)` and an injectable HTTP transport.
- Produces: `ArcaA13Client.dummy()`, `get_id_persona_list_by_documento(documento: str) -> list[str]`, and `get_persona(id_persona: str) -> ArcaPerson`; raises safe `ArcaConfigurationError`, `ArcaValidationError`, or `ArcaUnavailableError`.

- [ ] **Step 1: Write failing credential and routing tests**

Generate short-lived PEM and PFX fixtures with `cryptography`; assert credential loading, environment endpoint selection, service id `ws_sr_padron_a13`, SOAP operation names, normalized return types, safe parsing errors, and that errors never include key/certificate contents.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/test_arca_a13_client.py -q`

Expected: collection FAIL because `accounts.arca_a13` does not exist.

- [ ] **Step 3: Implement immutable settings, credential loaders, and CMS signing**

Load PEM with `serialization.load_pem_private_key`/`x509.load_pem_x509_certificate` or PFX with `pkcs12.load_key_and_certificates`. Build the WSAA TRA XML for `ws_sr_padron_a13` and sign DER CMS using `pkcs7.PKCS7SignatureBuilder` and SHA-256.

- [ ] **Step 4: Implement ticket cache and SOAP operations**

Cache token/sign before their server expiration under a key derived from environment, represented CUIT, certificate fingerprint and service id. POST XML SOAP envelopes through the injected transport; parse WSAA credentials and A13 `dummy`, `idPersona`, `numeroDocumento`, `estadoClave`, name and tax/person fields without returning raw XML to callers.

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && pytest tests/test_arca_a13_client.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/arca_a13.py backend/tests/test_arca_a13_client.py
git commit -m "feat: add ARCA A13 SOAP client"
```

### Task 4: Automatic DNI/CUIT fiscal resolution and billing persistence

**Files:**
- Create: `backend/accounts/fiscal_identity.py`
- Create: `backend/tests/test_fiscal_identity.py`
- Modify: `backend/accounts/serializers.py`
- Modify: `backend/tests/test_accounts.py`

**Interfaces:**
- Consumes: `get_arca_a13_adapter()` derived from encrypted integration configuration and `normalize_cuit`.
- Produces: `resolve_fiscal_identifier(raw_identifier: str) -> str`, returning only a validated 11-digit CUIT for persistence.

- [ ] **Step 1: Write failing decision-table tests**

Cover: formatted/unformatted 11-digit CUIT calls only `get_persona`; 7/8-digit DNI calls resolver then person lookup; other lengths fail; multiple/no CUIT candidates fail; DNI/document mismatch or inactive `estadoClave` fails; unavailable configured service is retryable; disabled/incomplete service accepts a checksum-valid CUIT locally but rejects DNI with guidance to enter full CUIT.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/test_fiscal_identity.py -q`

Expected: collection FAIL because the resolver does not exist.

- [ ] **Step 3: Implement configuration factory and exact branch order**

Implement:

```python
digits = only_digits(raw_identifier)
if len(digits) == 11:
    cuit = normalize_cuit(digits)
elif len(digits) in {7, 8}:
    cuit = require_single(adapter.get_id_persona_list_by_documento(digits))
    cuit = normalize_cuit(cuit)
else:
    raise FiscalIdentityError("Ingresá un DNI de 7 u 8 dígitos o un CUIT de 11 dígitos.")
```

Only after selecting `cuit`, call `get_persona(cuit)` when ARCA is ready and validate the returned identifiers/status.

- [ ] **Step 4: Integrate the resolver into `BillingProfileSerializer`**

Replace `validate_cuit` local-only normalization with `resolve_fiscal_identifier`; create/update must call `BillingProfile.set_cuit` only after successful resolution. Convert domain validation failures into field errors and provider outages into a retryable API error without persisting partial data.

- [ ] **Step 5: Verify GREEN and persistence rollback**

Run: `cd backend && pytest tests/test_fiscal_identity.py tests/test_accounts.py -q`

Expected: PASS and no billing profile is created/updated on ARCA failure.

- [ ] **Step 6: Commit**

```bash
git add backend/accounts/fiscal_identity.py backend/accounts/serializers.py backend/tests/test_fiscal_identity.py backend/tests/test_accounts.py
git commit -m "feat: resolve fiscal identity automatically through ARCA"
```

### Task 5: Real integration test endpoint and fiscal-profile feedback

**Files:**
- Modify: `backend/backoffice/views.py`
- Modify: `backend/tests/test_backoffice_integrations.py`
- Modify: `frontend/components/account/fiscal-profiles.tsx`
- Modify: `frontend/tests/fiscal-profiles.test.tsx`

**Interfaces:**
- Consumes: `ArcaA13Client.dummy()` and the billing profile API from Task 4.
- Produces: management test result for `arca_a13`; UI label `CUIT o DNI`; status text `Validando con ARCA…` during save.

- [ ] **Step 1: Write failing backend test-endpoint tests**

Assert that testing a complete ARCA integration calls `dummy`, a successful response returns HTTP 200, missing credentials returns a configuration error, and remote unavailability returns a safe non-secret error.

- [ ] **Step 2: Verify backend RED**

Run: `cd backend && pytest tests/test_backoffice_integrations.py -q`

Expected: FAIL because the generic endpoint does not call ARCA.

- [ ] **Step 3: Wire the ARCA test branch**

Resolve the saved configuration, build `ArcaA13Client`, call `dummy`, and map adapter exceptions to existing management test response conventions.

- [ ] **Step 4: Verify backend GREEN**

Run: `cd backend && pytest tests/test_backoffice_integrations.py -q`

Expected: PASS.

- [ ] **Step 5: Write failing fiscal-profile UI tests**

Assert the field is labeled `CUIT o DNI`, accepts formatted values, shows `Validando con ARCA…` while POST is pending, renders the backend field message on validation failure, and refreshes with masked CUIT on success.

- [ ] **Step 6: Verify frontend RED**

Run: `cd frontend && pnpm exec vitest run tests/fiscal-profiles.test.tsx`

Expected: FAIL because the current form says `CUIT` and only shows `Guardando…`.

- [ ] **Step 7: Implement fiscal-profile copy and pending/error states**

Keep a single automatic submit button; set `inputMode="numeric"`, change the label/help copy, show the ARCA validation pending state, and render the API-provided `cuit` field message without exposing transport details.

- [ ] **Step 8: Verify frontend GREEN**

Run: `cd frontend && pnpm exec vitest run tests/fiscal-profiles.test.tsx`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/backoffice/views.py backend/tests/test_backoffice_integrations.py frontend/components/account/fiscal-profiles.tsx frontend/tests/fiscal-profiles.test.tsx
git commit -m "feat: test ARCA integration and validate fiscal profiles"
```

### Task 6: Regression, security, and production-build verification

**Files:**
- Modify only files required by failures directly caused by Tasks 1-5.

**Interfaces:**
- Consumes: all prior task deliverables.
- Produces: verified backend/frontend builds with no credential disclosure and unchanged RENAPER bypass behavior.

- [ ] **Step 1: Run focused backend regression suites**

Run: `cd backend && pytest tests/test_arca_a13_client.py tests/test_fiscal_identity.py tests/test_backoffice_integrations.py tests/test_identity_configuration.py tests/test_accounts.py -q`

Expected: PASS.

- [ ] **Step 2: Run backend static checks and full tests**

Run: `cd backend && ruff check . && pytest -q`

Expected: PASS.

- [ ] **Step 3: Run focused frontend suites**

Run: `cd frontend && pnpm exec vitest run tests/identity-checkout-bypass.test.tsx tests/management-integrations.test.tsx tests/fiscal-profiles.test.tsx`

Expected: PASS.

- [ ] **Step 4: Run frontend lint, full tests, and production build**

Run: `cd frontend && pnpm lint && pnpm test -- --run && pnpm build`

Expected: PASS.

- [ ] **Step 5: Inspect the final diff for secret handling and scope**

Run: `git diff --check && git status --short && git diff --stat HEAD~5..HEAD`

Expected: no whitespace errors; no certificate, key, PFX, password, token, sign, or raw SOAP fixture committed; user-owned `marketing/` remains untouched.

- [ ] **Step 6: Record any verification-only repair**

If a regression caused by these changes required a repair, commit only the affected files with:

```bash
git commit -m "fix: close ARCA fiscal identity regressions"
```

