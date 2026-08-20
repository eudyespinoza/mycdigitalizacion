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
