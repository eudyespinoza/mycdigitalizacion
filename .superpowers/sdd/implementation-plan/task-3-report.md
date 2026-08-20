# Task 3 implementation report: external providers and checkout

## Outcome

Implemented the single-store external-provider layer, checkout orchestration, payment security,
shipping and stock-reservation lifecycle on `feat/ecommerce-foundation`. No frontend files were
changed and no marketplace OAuth, fees, commissions or multi-store behavior was introduced.

The implementation includes:

- Typed, injectable provider failures and a bounded-retry JSON HTTP boundary with explicit
  connect/read timeout values.
- Andreani locality sync into a bounded CP4/CPA8 lookup cache.
- GeoRef geocode/reverse-geocode adapters that omit floor, apartment and notes and persist only a
  response summary/confidence.
- Disabled/configurable SID behavior, persisted consent/attempt/audit state and reasoned staff-only
  manual approval.
- Deterministic rotation-aware guillotine packing using inner dimensions, tare/max weight and
  multiple parcels, with an explicit `cannot_pack` result.
- Correo Argentino authentication, aggregate multi-parcel quotes, 15-minute quote cache,
  exact/percentage surcharges, free-shipping threshold, shipment import, label and tracking
  interfaces. Disabled delivery does not affect pickup checkout.
- Mercado Pago Checkout Pro preferences and server-side payment fetch/refund with ARS, UUID
  external references, HTTPS returns, 20-minute expiry and idempotency headers.
- Transactional checkout revalidation of verified email, identity, cart pricing/promotions,
  address/quote and stock. `pending_identity` orders create neither reservations nor payment
  preferences; resume performs the checks again.
- Payment transaction and webhook-event persistence with unique provider identifiers,
  idempotency keys and raw-body hashes. Webhooks persist/deduplicate before HMAC/timestamp
  validation, queue processing, then fetch payment state server-to-server.
- Amount, currency, collector, live-mode, external-reference and order validation. Mismatches and
  expired-reservation payment races move to `needs_attention`; out-of-order pending events cannot
  downgrade a paid order.
- Idempotent total refunds, automatic pre-fulfillment stock restoration and post-shipment
  `return_required` recording.
- Public/staff API actions for locality lookup, geocoding, identity validation/manual review,
  shipping quotes, checkout confirm/resume, Mercado Pago webhook, persisted payment status,
  shipment, label, tracking and refund.
- Celery beat tasks for Andreani sync, reservation expiry, payment and tracking reconciliation,
  safe notification retry state and verification-challenge expiry. Development and production
  Compose files include the beat service and environment-only provider configuration.
- Staff-only provider-failure diagnostics with safe customer-facing Spanish API messages. Provider
  secrets and arbitrary raw provider payloads are not persisted or logged.

No Python dependency changed, so the existing hash-locked requirements files remain unchanged.

## TDD evidence

Focused RED runs were captured before each corresponding implementation slice:

1. `APP_ENV=test python -m pytest tests/test_checkout_providers.py -q`
   - RED: `6 failed` because postal, GeoRef, distance, packing and quote-expiry modules did not yet
     exist.
   - Next RED: `4 failed, 6 passed` for missing SID, Correo, Mercado Pago and signature contracts.
   - GREEN: `10 passed`, later `11 passed` after a new combination-packing test first failed with
     two parcels instead of one.
2. `APP_ENV=test python -m pytest tests/test_checkout_domain.py -q`
   - RED: `8 failed` for missing identity persistence/manual review, checkout, webhook and payment
     lifecycle behavior.
   - Next RED: `2 failed, 8 passed` for missing Andreani mapping and refund policy.
   - GREEN: `10 passed`.
3. `APP_ENV=test python -m pytest tests/test_checkout_api.py -q`
   - RED: `4 failed` (three missing routes and the old checkout boundary returning 503).
   - GREEN: `4 passed`.

The focused final Task 3 boundary was `24 passed` before the additional packing regression and
PostgreSQL race coverage were added.

## Final verification evidence

All commands were run from the current worktree after the final implementation changes:

- SQLite/full backend suite:
  - `APP_ENV=test python -m pytest -q`
  - Result: `103 passed, 9 skipped in 19.79s`.
  - Skips are the PostgreSQL-only cases plus the credential-gated sandbox smoke test.
- PostgreSQL 17 concurrency suite:
  - `docker compose run --rm -e USE_POSTGRES_TEST_DB=true backend pytest -m postgresql -q`
  - Result: `10 passed, 102 deselected in 55.04s`.
  - Includes simultaneous payment approval/reservation expiry and the existing inventory/cart
    locking cases.
- Lint:
  - `ruff check .`
  - Result: `All checks passed!`.
- Django/migrations/OpenAPI in the Compose backend:
  - `python manage.py check`
  - Result: `System check identified no issues (0 silenced).`
  - `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.
  - `python manage.py spectacular --validate --file /tmp/task3-openapi.yaml`
  - Result: exit code 0.
- Compose validation:
  - `docker compose config --quiet`
  - production `docker compose -f compose.prod.yaml config --quiet` with required production
    environment values
  - Result: both exit code 0.
- Diff hygiene:
  - `git diff --check`
  - Result: exit code 0.

## Operational follow-up / concerns

- No SID, Correo Argentino or Mercado Pago sandbox credentials were present. The smoke test is
  deliberately marked `sandbox` and skipped without credentials; no live success was fabricated.
- Before production enablement, operators must validate the configured SID and MiCorreo endpoint
  field mappings against their issued QA accounts and perform an end-to-end Mercado Pago sandbox
  webhook/refund run.
- Provider modes default to disabled/QA. Production credentials remain environment-only and are
  never stored in database rows.

## Fix Round 1 (independent review `5d7f070`)

### Regression TDD evidence

The 19 REQUIRED findings were grouped into observable provider, checkout/identity, payment
recovery, shipment/API, and configuration/audit regressions before implementation changes:

- RED: `APP_ENV=test python -m pytest -q tests/test_task3_round1_regressions.py`
  - Result: `22 failed`.
  - The failures reproduced the MiCorreo wire mismatch, non-idempotent confirmation/resume,
    incomplete quote binding, packing order dependence, webhook poisoning/query mismatch,
    missing retry sweep/reconciliation, tautological payment binding, unsafe refund finality,
    consent/identity audit defects, non-exact CPA8, incomplete disabled/timeout boundaries,
    shipment/API races, startup validation gaps, and mutable operational admin records.
- Additional focused RED cases were captured before their recovery slices:
  - stale queued webhook recovery, fiscal-profile resume revalidation, and pending-refund replay:
    `3 failed`;
  - typed SID API failure: `1 failed`;
  - stable missing-order API code: `1 failed`.
- GREEN: `APP_ENV=test python -m pytest -q tests/test_task3_round1_regressions.py`
  - Result: `25 passed in 2.70s`.

### REQUIRED finding resolution map

1. **MiCorreo v1 contract** — QA defaults to
   `https://apitest.correoargentino.com.ar/micorreo/v1`; `/token` uses HTTP Basic and reads
   `token`; rates send `customerId`, origin/destination CP and integer dimensions and parse the
   documented `rates` array; import uses `/shipping/import`; tracking uses GET
   `/shipping/tracking` with `shippingId`. The public PDF exposes no label route, so label now
   returns typed `not_supported`/HTTP 501 instead of inventing one.
2. **Checkout/resume idempotency** — checkout accepts a required UUID idempotency key, enforced
   uniquely per user. Sequential and concurrent retries return the same order/transaction; resume
   locks and advances the original order and cannot create a replacement.
3. **Authoritative quote fingerprint** — the digest now includes variant prices, dimensions,
   weight, calculated discount/totals, coupon, address fields and final parcel dimensions.
4. **Packing determinism/dimensions** — equal-volume units use a canonical dimension/SKU/weight
   tiebreak; parcels retain selected box length/width/height for carrier rating.
5. **Webhook signed-ID/poisoning** — ingestion receives signed query `data.id`, lowercases it for
   the manifest, uses configured tolerance, and allows a correctly signed retry to replace a prior
   rejected collision without suppressing processing.
6. **Durable webhook retries** — provider failures have bounded Celery autoretry; unexpected
   failures return events to `queued`; a beat sweeper re-enqueues stale `queued` and `processing`
   events and refreshes their claim timestamp.
7. **Lost webhook reconciliation** — pending transactions without `payment_id` are searched by
   provider `external_reference`; transactions with an ID continue to use direct payment fetch.
8. **Independent order binding/terminal states** — preferences store provider metadata
   `order_id`; payment application requires it to match the local public order UUID. Expired
   payments fail; refunded/chargeback terminal states become `needs_attention` rather than being
   ignored or silently mutating stock.
9. **Refund safety/idempotency** — the order and existing idempotency record are locked before
   provider I/O; total refunds send an empty body (`amount=None`); stock/order/payment transitions
   occur only after provider `status=approved`; a pending result can be safely replayed with the
   same key to observe later approval.
10. **Consent/SID timeout** — checkout and direct SID validation require an explicit boolean and
    only affirmative consent creates an attempt with `consented_at`; timeout joins unavailable and
    not-configured in `pending_review`.
11. **Order-bound identity review** — checkout attempts reference their order; manual approval is
    limited to order-bound `pending_review` attempts with staff actor/reason; rejected attempts
    cannot be overridden; resume accepts only approval attached to that order.
12. **Exact CPA8** — CPA8 lookup filters only exact `cpa`; CP4 retains bounded postal-code lookup.
13. **Timeout/disabled contracts** — the standard-library transport applies the connect timeout
    while opening the socket and the read timeout after connect, with typed timeout/unavailable
    errors. Disabled carrier/payment adapters implement every scheduled/action interface and raise
    typed `not_configured`.
14. **Shipment locking/eligibility** — shipment creation locks the order, uses deterministic
    per-order/per-parcel idempotency identifiers, and requires shipping + verified identity + paid
    + unfulfilled + quoted parcels. PostgreSQL concurrency proves one carrier import/local row.
15. **Stable API/OpenAPI errors** — staff missing-order/shipment, ineligible shipment, refund,
    provider and unsupported-label paths return JSON codes; signed webhook query/body and all
    action response statuses are represented in validated OpenAPI.
16. **Compose/startup validation** — backend/worker/beat receive both MiCorreo URLs, customer/origin,
    surcharge/free-shipping values and webhook tolerance. Production startup validates provider
    modes, paired credentials, required enabled-carrier fields, HTTPS URLs and numeric policy.
17. **Fiscal ownership/snapshot** — checkout requires an owned billing profile, locks/revalidates
    it at confirmation, stores encrypted/hash/masked fiscal snapshot fields, and rejects resume if
    ownership or current fiscal fields changed.
18. **Append-only admin** — payment, webhook, refund, shipment, provider-failure, notification and
    identity audit models have all fields read-only and no add/change/delete admin permissions.
19. **Ruff** — the original `UP038` defect and all new lint findings are resolved; final
    `ruff check .` is clean.

No OPTIONAL review finding was deliberately implemented.

## Fix Round 2 (remaining REQUIRED partials)

### Regression TDD evidence

The eight remaining partials from the appended Fix Round 1 verdict were reproduced before their
implementations changed:

- RED: `APP_ENV=test python -m pytest -q tests/test_task3_round2_regressions.py --maxfail=20`
  - Result: `14 failed, 1 passed`.
  - The failures reproduced the unbound identity/preference rollback boundary, stale active
    webhook claim, raw HTTP protocol exceptions and misclassified 400/402 responses, lost parcel
    import progress/finalization, rejected-SID HTML 500, incomplete webhook schema, permissive
    provider startup, and public fiscal ciphertext/hash leakage.
- PostgreSQL concurrency regressions were added for a globally reused refund key across two
  different orders and durable multi-parcel recovery. The original PostgreSQL run also exposed
  PostgreSQL's prohibition on `SELECT FOR UPDATE` across the nullable `shipping_quote` outer join;
  the shipment lock was narrowed to the authoritative `Order` row before the final run.
- GREEN: `APP_ENV=test python -m pytest -q tests/test_task3_round2_regressions.py`
  - Result: `16 passed in 5.58s`.

### REQUIRED partial resolution map

- **F2 — provider-success/database-failure checkout recovery:** checkout now derives the order
  UUID, payment external reference, and Mercado Pago preference idempotency key from the user and
  checkout idempotency key. A retry after rollback therefore reaches the exact same provider
  preference boundary. Rolled-back attempts delete only their still-unbound identity audit, while
  successful, pending-review, sequential, and concurrent flows retain one order-bound attempt.
  Resume uses the same deterministic payment identifiers on the original pending order.
- **F6 — active webhook claims:** the `queued -> processing` claim now atomically writes an
  explicit current `updated_at` with the status under the event row lock. A provider-I/O regression
  invokes the stale sweep during a real active claim and proves it is not requeued.
- **F9 — cross-order refund-key collision:** refund creation uses an inner savepoint around the
  global unique insert. A concurrent loser reloads and locks the committed winner, then returns the
  stable `refund_idempotency_conflict` outcome without an uncaught `IntegrityError` or a second
  provider refund call. Same-order replay behavior remains unchanged.
- **F13 — protocol and validation failures:** all `http.client.HTTPException` subclasses,
  including bad status lines, incomplete reads, and remote disconnects, are converted to typed
  provider failures without leaking response content. HTTP 400 and 402 are typed rejections and
  are never retried as availability failures.
- **F14 — durable multi-parcel import:** migration `0011_shipment_parcel_import` adds a durable
  per-parcel intent with deterministic external/idempotency identifiers, persisted parcel
  snapshot, status, and safe provider summary. Shipment and every parcel intent commit before
  remote I/O; each imported parcel commits independently; retries lock each intent, skip imported
  parcels, reuse the same key for incomplete ones, and finalize separately. A beat task resumes
  `importing` shipments. SQLite and PostgreSQL regressions prove parcel-1/provider failure recovery,
  final-database-failure recovery, no repeated completed-parcel call, and one carrier call under
  concurrency.
- **F15 — SID rejection and webhook OpenAPI:** explicit SID rejection at checkout now returns
  HTTP 422 JSON with stable `identity_rejected` and a safe Spanish detail. The validated webhook
  operation documents required query `data.id`, required `x-signature` and `x-request-id` headers,
  the required `id`/`type`/`data.id` body, and 200/202/403 response schemas.
- **F16 — fail-closed provider startup:** provider booleans accept only literal `true`/`false` in
  every environment. Any configured/live Mercado Pago instance requires access token, webhook
  secret, and collector ID; enabled Correo Argentino validates its mode, issued credentials,
  customer/origin, and HTTPS environment URL before startup. Development Compose now forwards the
  same provider URLs, webhook tolerance, carrier identity, and shipping-policy fields to backend,
  worker, and beat; production wiring remains intact.
- **F17 — public fiscal privacy:** orders retain the protected fiscal snapshot internally for audit
  and resume validation, but the public order serializer now uses an explicit nested allowlist of
  label, legal name, tax condition, and masked CUIT. `profile_id`, ciphertext, and hash are absent
  from list/detail API output and their OpenAPI schema.

All eight REQUIRED partials are resolved. No REQUIRED Fix Round 2 item remains open, and no
OPTIONAL review item was deliberately implemented.

### Fix Round 2 final verification

- Focused regressions: `16 passed in 5.58s`.
- Full SQLite suite: `144 passed, 13 skipped in 43.08s`.
- PostgreSQL 17 suite:
  `docker compose run --rm -e APP_ENV=test -e USE_POSTGRES_TEST_DB=true backend python -m pytest -q -m postgresql`
  -> `14 passed, 143 deselected in 83.89s`, including checkout/shipment concurrency,
  cross-order refund collision, and parcel recovery.
- `ruff check .` -> `All checks passed!`.
- Compose/PostgreSQL `python manage.py check` -> `System check identified no issues (0 silenced)`.
- Compose/PostgreSQL `python manage.py makemigrations --check --dry-run` ->
  `No changes detected`.
- `python manage.py spectacular --validate --file /tmp/task3-round2-openapi-final.yaml` ->
  exit code 0 with no warnings.
- `docker compose -f compose.yaml config --quiet` and production Compose with required production
  interpolation values -> both exit code 0.
- `git diff --check` -> exit code 0; Git emitted only existing Windows CRLF conversion advisories.

### Remaining operational concerns

- SID, MiCorreo QA, and Mercado Pago sandbox credentials were still unavailable. Credential-gated
  smoke coverage remains skipped; no external success was fabricated.
- MiCorreo's published v1 contract still exposes no label route, so the existing typed
  `not_supported` behavior remains the safe boundary.
- Deterministic Mercado Pago keys and carrier parcel keys assume the providers honor their
  published idempotency contracts; production rollout should retain provider-side reconciliation
  monitoring for the small crash window after remote success and before a local commit.

### Fix Round 1 final verification

- Focused regression suite: `25 passed`.
- Full SQLite suite: `128 passed, 11 skipped in 23.83s`.
- PostgreSQL 17 suite:
  `docker compose run --rm -e APP_ENV=test -e USE_POSTGRES_TEST_DB=true backend python -m pytest -q -m postgresql`
  -> `12 passed, 127 deselected in 63.13s`, including concurrent checkout idempotency and
  concurrent shipment creation/provider-call locking.
- `ruff check .` -> `All checks passed!`.
- `python manage.py check` -> `System check identified no issues (0 silenced).`.
- Compose/PostgreSQL `python manage.py makemigrations --check --dry-run` ->
  `No changes detected`.
- `python manage.py spectacular --validate --file <temporary-path>` -> exit 0.
- `docker compose -f compose.yaml config --quiet` and production Compose with required production
  interpolation values -> both exit 0.
- `git diff --check` -> exit 0.

### Remaining operational concerns

- No SID, MiCorreo QA, or Mercado Pago sandbox credentials were available, so credential-gated
  smoke tests remain skipped and no external success was fabricated.
- MiCorreo's published v1 PDF has no label endpoint. The API now fails safely with
  `not_supported`; label generation must remain disabled until Correo Argentino provides a
  documented account-specific contract.
- Provider secrets remain environment-only; request logs and persisted summaries contain no raw
  credentials, DNI/CUIT plaintext, webhook bodies, or arbitrary provider payloads.
