# ARCA A13 fiscal identity integration

Date: 2026-08-27

## Objective

Add an optional ARCA Padrón A13 integration that resolves and validates fiscal identity while preserving the current checkout bypass rule when the integration is disabled or incomplete. The customer must not need to choose between DNI and CUIT modes or press a separate conversion button.

The same delivery also makes the initial checkout error actionable by linking directly to personal and fiscal data screens.

## User experience

The fiscal profile field is labeled `CUIT o DNI` and accepts formatted or unformatted digits.

- Eleven normalized digits are treated as a CUIT. The backend validates its checksum and calls A13 `getPersona` directly.
- Seven or eight normalized digits are treated as a DNI. The backend calls `getIdPersonaListByDocumento`, obtains the assigned CUIT, and then calls `getPersona` with that CUIT.
- Any other normalized length is rejected with a field-level validation message.

Resolution happens automatically while saving the fiscal profile. There is no `Obtener CUIT` button. During a configured ARCA request the form shows `Validando con ARCA…`; a successful response saves the resolved CUIT in the existing encrypted fiscal-profile field and continues normally.

When checkout cannot continue because personal identity data is incomplete, the alert contains two visible actions:

- `Completar datos personales` → `/cuenta`
- `Cargar datos fiscales` → `/cuenta/fiscal`

The alert and checkout stage remain in the right-hand content column instead of the alert displacing the form below the stepper.

## Why this is a resolver, not a local converter

CUIT/CUIL prefixes for people can be 20, 23, 24, 27, or future values and are assigned without a gender-derived deterministic rule. The application therefore never guesses a CUIT from a DNI. It uses the A13 method designed to resolve a person identifier by document.

## Management configuration

A new provider `arca_a13` appears under Integraciones with the label `Identidad fiscal ARCA · Padrón A13`.

Public configuration:

- `represented_cuit`: CUIT represented in A13 calls.
- Environment: testing or production, using the corresponding official WSAA and A13 endpoints.
- Optional advanced WSAA and A13 endpoint overrides, empty by default.

Protected, write-only configuration:

- X.509 certificate file (`.crt` or `.pem`).
- Private-key file (`.key` or `.pem`).
- Optional private-key passphrase.
- Alternatively, a PKCS#12 bundle (`.pfx` or `.p12`) and its optional password.

The editor accepts either certificate-plus-key or PKCS#12, never requires both, and sends file contents through the existing encrypted integration-secret channel. Binary PKCS#12 content is base64 encoded before submission. Responses expose only configured/not-configured flags.

The existing `Verificar configuración` action validates the credential bundle, requests a WSAA ticket for `ws_sr_padron_a13`, and invokes A13 `dummy`. It stores only the result status and a safe message.

## Readiness and bypass rule

ARCA is ready only when all of the following are true:

- The integration exists and is enabled.
- `represented_cuit` is a checksum-valid CUIT.
- Either a valid certificate/private-key pair or a readable PKCS#12 bundle is present.
- The selected environment is valid.

If no ARCA configuration exists, it is disabled, or it is incomplete:

- Eleven-digit CUIT input is validated locally and saved without contacting ARCA.
- Seven/eight-digit DNI input cannot be resolved without ARCA and returns an actionable message asking for the full CUIT.
- Checkout does not require ARCA validation and continues under the existing bypass policy.

If ARCA is enabled and ready, fiscal-profile saving is validated through A13. Invalid or unmatched identity data is rejected. A temporary WSAA/A13 outage produces a retriable provider error and does not persist an unvalidated change.

## Backend architecture

### ARCA adapter

A dedicated adapter owns:

1. Credential loading for PEM and PKCS#12.
2. WSAA LoginCms request creation and CMS signing.
3. Ticket parsing and caching.
4. SOAP calls to A13 `dummy`, `getIdPersonaListByDocumento`, and `getPersona`.
5. XML parsing and conversion to a small internal fiscal-identity result.

Official environment endpoints are constants. Network access is injected behind a transport boundary so tests use real request/response parsing without reaching ARCA.

WSAA tickets are cached by environment, certificate fingerprint, represented CUIT, and service ID. Cache expiry is earlier than the ticket expiration returned by WSAA. Tokens, signatures, certificates, keys, passwords, full DNI, and full CUIT are never logged.

### Fiscal-profile validation

The billing-profile serializer delegates input normalization and optional provider resolution to a fiscal-identity service:

1. Normalize digits.
2. Resolve DNI to CUIT only when needed.
3. Validate the CUIT checksum.
4. Fetch the A13 person.
5. Confirm the returned identifier matches the resolved/requested CUIT.
6. For DNI input, confirm `numeroDocumento` matches the supplied DNI.
7. Require an acceptable active key status.
8. Save the final CUIT using the existing encrypted `BillingProfile.set_cuit` path.

The service returns only the resolved CUIT and safe display metadata. Existing encrypted storage and masked API responses remain unchanged, so no fiscal identifier is exposed by management APIs or logs.

### Provider selection

ARCA does not replace SID RENAPER. RENAPER remains responsible for checkout personal-identity verification. ARCA is responsible for resolving and validating fiscal identity on billing profiles. Each integration has its own readiness and bypass decision.

## Error handling

- Invalid length or checksum: field validation error.
- DNI entered while ARCA is unavailable: request the full CUIT; do not guess.
- No A13 match: explain that no CUIT could be found for the DNI.
- Multiple A13 identifiers: reject safely and request a full CUIT rather than choosing silently.
- A13 person/document mismatch or inactive key: reject the fiscal profile.
- Invalid certificate/key/password: mark integration verification as error without exposing cryptographic details.
- WSAA/A13 timeout or malformed SOAP: return a retriable provider error and record a sanitized provider failure.

## Security

- Reuse the encrypted `IntegrationConfiguration.sealed_secrets` storage.
- Validate file size and supported credential formats before sealing.
- Never return credential material after save.
- Audit only changed secret-field names, environment, enabled state, and safe test result.
- Do not include ticket, signature, certificate subject details, DNI, or CUIT in exception messages or telemetry.
- Keep provider requests server-side and require authenticated ownership of the fiscal profile.

## Testing

Backend tests cover:

- Integration presence, encrypted write-only credential storage, and readiness rules.
- PEM and PKCS#12 loading, including wrong passwords and mismatched keys.
- WSAA request signing, ticket parsing, cache expiry, and environment endpoints.
- A13 SOAP parsing for `dummy`, document resolution, direct CUIT lookup, no match, multiple matches, inactive key, timeout, and malformed response.
- Eleven-digit input skips `getIdPersonaListByDocumento` and calls `getPersona` once.
- Seven/eight-digit input resolves first and then calls `getPersona` with the returned CUIT.
- Disabled/incomplete integration bypasses validation for a complete CUIT.
- Disabled/incomplete integration never invents a CUIT from a DNI.
- Fiscal identifiers and credential contents are absent from responses, logs, and audit metadata.

Frontend tests cover:

- Integration fields, credential file handling, configured indicators, and environment selection.
- Automatic fiscal form saving with CUIT or DNI and the validating state.
- Field-level errors returned by the resolver.
- Checkout alert links to both `/cuenta` and `/cuenta/fiscal`.
- Desktop and mobile checkout layout keeps the alert compact and the data stage visible.

## Deployment and rollback

The integration reuses the existing integration-configuration table and encrypted billing-profile CUIT storage. No schema migration is required unless implementation reveals a need for persistent provider metadata; that metadata is intentionally out of scope for this design.

Rollout order:

1. Deploy code with `arca_a13` disabled by default.
2. Upload credentials and represented CUIT in management.
3. Verify configuration against the selected environment.
4. Enable the integration.
5. Run a controlled DNI and CUIT validation before general use.

Rollback is disabling `arca_a13`; complete CUIT input immediately returns to local checksum validation and existing checkout bypass behavior.
