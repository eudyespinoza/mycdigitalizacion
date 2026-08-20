# Task 3 independent review

Review range: `41dfb3e..08c64275fd49d0ed1553baf406bcdadeea242b68`

Reviewed against: `task-3-brief.md` and `PRODUCT.md`

Implementation report independently checked: `task-3-report.md`

## Verdict

- **SPEC COMPLIANCE: FAIL**
- **CODE QUALITY: FAIL**
- **Required findings: 19**
- **Optional findings: 4**

The implementation has a correct PostgreSQL row-locking basis for last-unit reservations (`commerce/services.py:225-275`) and the persisted redirect status endpoint ignores provider query parameters. GeoRef payload minimization, quote expiry, amount/currency/collector/live-mode comparisons, and the basic pre-fulfillment versus post-shipment stock policy are present. However, the real MiCorreo contract cannot work, retries can duplicate checkout or strand paid orders, identity/manual-review audit state is not trustworthy, and multiple required API/provider recovery paths return 500 or silently remain pending.

## REQUIRED

1. **[P1, confidence 10/10] The MiCorreo adapter does not implement Correo Argentino's published API contract.**
   - Code: `backend/config/settings.py:181-186` defaults QA and production to the production host; `backend/commerce/shipping.py:56-68` sends JSON credentials and expects `access_token`; `backend/commerce/shipping.py:73-89` sends `{postal_code, parcel}` and expects top-level `{price, service}`; `backend/commerce/shipping.py:114-132` calls `/shipments`, `/shipments/{id}/label`, and `/tracking/{tracking_number}`; `backend/commerce/shipping.py:219-236` expects shipment `id` and `tracking_number` from import.
   - Authoritative evidence: Correo Argentino's [MiCorreo API PDF](https://www.correoargentino.com.ar/MiCorreo/public/img/pag/apiMiCorreo.pdf), pp. 1-2, 8-18, specifies QA `https://apitest.correoargentino.com.ar/micorreo/v1`, HTTP Basic auth to `/token` with response field `token`, required `customerId`, origin/destination CP and dimensions for `/rates`, `/shipping/import`, and GET `/shipping/tracking` with `shippingId`. The public contract has no `/shipments/{id}/label` route.
   - Test evidence: `backend/tests/test_checkout_providers.py:146-169` uses invented responses (`access_token`, top-level `price/service`) rather than faithful HTTP fakes. A live recording of the adapter produced JSON auth and the dimensionless rate body exactly as the code indicates.
   - Impact: QA auth, rates, import, label, and tracking fail with issued MiCorreo credentials. This is not a credential-gated smoke-test concern; the wire contract itself is wrong.

2. **[P1, confidence 10/10] Checkout and resume have no idempotency boundary.**
   - Code: `backend/commerce/serializers.py:109-113` accepts no idempotency key; `backend/commerce/checkout.py:123-181` always creates a new order, reservations, transaction, UUIDs and preference; `backend/commerce/checkout.py:190-219` implements resume by calling `confirm_checkout()` again, creating a second order instead of resuming the pending one.
   - Reproduction: two identical `confirm_checkout()` calls produced two different order IDs, 2 transactions, and 2 active reservations for the same cart.
   - Impact: browser retries/double-clicks can reserve and potentially charge the cart twice. A resumed manual-review order is left orphaned while a new order is returned.

3. **[P1, confidence 10/10] Shipping quotes remain valid after price, promotion, coupon, or package-dimension changes.**
   - Code: `backend/commerce/checkout.py:39-42` hashes only `(variant_id, quantity)`; `backend/commerce/shipping.py:144-156` reuses a cached quote by that hash before recalculating totals; `backend/commerce/checkout.py:56-61` accepts the quote using the same incomplete hash.
   - Reproduction: changing a variant from ARS 100 to ARS 1 and changing its length from 1 cm to 100 cm left `cart_fingerprint()` unchanged.
   - Impact: the order is repriced but shipping is not. Free-shipping threshold decisions and carrier parcel costs can be stale at the irreversible checkout boundary.

4. **[P1, confidence 10/10] Packing is not deterministic for equal-volume items and drops dimensions before carrier rating.**
   - Code: `backend/commerce/packing.py:94-100` sorts units only by volume, preserving caller/database order for ties; `backend/commerce/shipping.py:168-188` does not order cart lines and serializes only box code, weight, and SKU list, not parcel dimensions.
   - Reproduction: permuting three 12 cm3 items `(1,2,6)`, `(1,3,4)`, `(2,2,3)` changed the result between one `b2` parcel and two `b1+b2` parcels.
   - Impact: identical carts can receive different parcel counts/rates. The resulting parcel payload also lacks the dimensions required by MiCorreo.

5. **[P1, confidence 10/10] Webhook HMAC ingestion is vulnerable to invalid-event deduplication poisoning and does not follow the signed-ID contract exactly.**
   - Code: `backend/commerce/payments.py:81-99` inserts the unique event before validation and returns every collision as a duplicate; `backend/commerce/payments.py:83-86,100-106` derives the signed data ID from the JSON body; `backend/api_views.py:1053-1062` never passes the signed `data.id` query parameter; `backend/config/settings.py:176-178` defines a tolerance setting that is never passed, so `payments.py:32-44` always uses 300 seconds.
   - Reproduction: an invalid delivery for `evt-guessable` followed by a correctly signed retry returned `duplicate=True`; the row stayed `rejected`, `signature_valid=False`, and no task was queued.
   - Authoritative evidence: Mercado Pago's [official webhook documentation](https://www.mercadopago.com.ar/developers/es/docs/your-integrations/notifications/webhooks) constructs the HMAC from the URL query parameter `data.id`, `x-request-id`, and `ts` (lowercasing alphanumeric URL IDs).
   - Impact: a header-stripped first delivery, process interruption, or guessed event ID can permanently suppress a valid payment notification.

6. **[P1, confidence 10/10] Transient webhook failures are marked retryable but never retried, while other exceptions can strand an event in `processing`.**
   - Code: `backend/commerce/payments.py:231-255` marks `processing` before the server-side fetch; `backend/commerce/tasks.py:35-49` resets provider failures to `queued` then raises, but has no `autoretry_for`, `self.retry`, or replacement enqueue; `backend/config/settings.py:193-217` has no queued/processing webhook sweep.
   - Impact: after the endpoint already returned 202, one Mercado Pago timeout can leave a paid order pending forever. `DoesNotExist`, `IntegrityError`, or worker termination after line 237 leaves `processing` permanently.

7. **[P1, confidence 10/10] Pending-payment reconciliation excludes the transactions it needs to recover after a lost webhook.**
   - Code: checkout creates `PaymentTransaction` without `payment_id` at `backend/commerce/checkout.py:162-181`; the ID is first assigned during webhook application at `backend/commerce/payments.py:193-195`; `backend/commerce/tasks.py:53-68` explicitly excludes null `payment_id`.
   - Impact: if the webhook is lost, reconciliation never queries Mercado Pago by preference/external reference, so the transaction stays pending indefinitely.

8. **[P1, confidence 9/10] The required payment-to-order check is a tautology, and externally changed terminal states are ignored.**
   - Code: `backend/commerce/payments.py:142-143` compares `transaction.order_id` with `transaction.order.pk`, two representations of the same local FK; `backend/commerce/mercadopago.py:69-89` sends no order ID metadata to validate. `backend/commerce/payments.py:186-219` handles approved/rejected and a subset of pending states but silently ignores terminal provider states such as refunded/charged-back/expired.
   - Impact: amount, currency, collector, live mode, and external reference are checked, but there is no independent provider order binding despite the brief's explicit requirement. Provider-side refunds/chargebacks do not update or alert the local order.

9. **[P1, confidence 10/10] Refund processing is neither transactionally idempotent nor conditional on a final approved refund.**
   - Code: `backend/commerce/payments.py:260-264` checks the idempotency key before acquiring the order lock and does not catch the concurrent unique-key race; `backend/commerce/payments.py:280-286` always supplies `amount` and accepts any response dictionary; lines 287-323 restore/release stock and mark the transaction/order refunded regardless of response status.
   - Reproduction: a provider response `{id: "r-1", status: "pending"}` restored stock and set `Order.payment_status="refunded"`.
   - Authoritative evidence: Mercado Pago's [Create refund reference](https://www.mercadopago.com.ar/developers/es/reference/online-payments/checkout-api-payments/create-refund/post) returns `status: approved` for success, and its [Checkout Pro refund guidance](https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/additional-settings/refunds-and-cancellations) says a total refund uses an empty request body; supplying `amount` requests a partial refund.
   - Impact: inventory can be resold before money is returned, while concurrent same-key requests can return 500 instead of the existing refund.

10. **[P1, confidence 10/10] SID consent audit can record consent that was omitted or explicitly denied, and SID timeouts do not enter manual review.**
    - Code: `backend/commerce/serializers.py:122-123` defaults omitted consent to true; checkout hardcodes `consent=True` at `backend/commerce/checkout.py:89`; `backend/commerce/identity_service.py:18-25` always writes `consented_at=now` before evaluating consent. It catches only not-configured/unavailable at lines 27-34, while `ProviderTimeout` is a separate type at `backend/providers.py:28-30`.
    - Impact: the audit cannot prove affirmative consent, and a routine timeout blocks rather than producing the required `pending_review` order with no reservation/payment.

11. **[P1, confidence 10/10] Manual approval is not bound to a pending order and can override explicit SID rejection.**
    - Code: `backend/commerce/identity_service.py:50-62` approves any attempt without requiring `pending_review`; `backend/commerce/checkout.py:190-202` accepts any historical approved attempt for the user; `backend/commerce/models.py:220-285,335-360` has no order-to-identity-attempt relationship.
    - Reproduction: `approve_identity_manually()` changed a `rejected` attempt with `sid_status=rejected` to `approved`.
    - Impact: an unrelated/old approval can resume a newer pending or rejected checkout, violating the explicit-rejection block and making the staff actor/reason audit non-attributable to a specific order.

12. **[P1, confidence 10/10] CPA8 lookup is not exact.**
    - Code: `backend/locations/services.py:58-63` queries `postal_code=CP4 OR cpa=CPA8` for CPA input.
    - Reproduction: with `C1414ABC` and `C1414DEF` stored under CP 1414, lookup for `C1414ABC` returned both rows.
    - Impact: customers can select the wrong locality even after entering a full CPA8. The existing tests use only one row for the CP and miss this case.

13. **[P1, confidence 9/10] The default HTTP boundary does not enforce separate connect/read timeouts, and disabled adapters do not satisfy their interfaces with typed failures.**
    - Code: `backend/providers.py:13,78-88` collapses `(3s,10s)` to one `urlopen(..., timeout=10s)` and can classify socket timeouts wrapped by `URLError` as unavailable; `backend/commerce/provider_config.py:11-17` lacks `fetch_payment/refund`; `backend/commerce/shipping.py:40-43` lacks import/label/tracking methods.
    - Impact: the explicit connect timeout is not real, timeout diagnostics are unreliable, and scheduled reconciliation can crash with `AttributeError` instead of a typed `not_configured` failure when a provider is disabled after records exist.

14. **[P1, confidence 10/10] Shipment creation is race-prone and does not enforce order eligibility.**
    - Code: `backend/commerce/shipping.py:211-233` performs an unlocked `hasattr` check, calls the provider with a fresh random idempotency key, then inserts the one-to-one row. It never checks shipping fulfillment method, verified identity, paid status, or fulfillment state.
    - Impact: concurrent actions can create two carrier shipments before one local insert fails, and staff can import unpaid, pending-identity, pickup, or already fulfilled orders.

15. **[P2, confidence 10/10] Several required API failure paths return HTML 500 responses instead of stable safe codes, and OpenAPI describes responses the code does not guarantee.**
    - Code: `backend/api_views.py:856-871` and `1018-1032` omit `ProviderError` handling; `_staff_order()` uses raw `.get()` at lines 619-622; label/tracking dereference a possibly absent shipment at lines 653 and 669; refund can raise uncaught `ValueError` from `backend/commerce/payments.py:272-273`.
    - Reproduction: POST to the staff shipment action for an unknown UUID returned HTTP 500 HTML, not JSON 404.
    - Contract evidence: action schemas at `backend/api_views.py:624-686` omit these actual 500s and several valid 400/404/502 outcomes; the webhook OpenAPI declaration at lines 1049-1052 omits its signed query parameters/body shape.

16. **[P2, confidence 10/10] Production containers ignore implemented provider controls, and provider enablement does not fail closed at startup.**
    - Code: `compose.prod.yaml:23-45,57-79,91-113` does not pass MiCorreo base URLs, shipping surcharge type/value, free-shipping threshold, or webhook tolerance to backend/worker/beat. `backend/config/settings.py:26-44` validates none of the provider modes/credentials/URLs when enabled.
    - Impact: `.env` changes for required operational pricing and endpoints have no effect in containers; invalid enabled configurations start successfully and fail only during customer/staff requests.

17. **[P2, confidence 9/10] Checkout never validates or snapshots a fiscal profile.**
    - Code: `backend/commerce/serializers.py:109-113` has no billing-profile selection; `backend/commerce/checkout.py:143` always passes `fiscal_snapshot={}` although fiscal profiles exist in `backend/accounts/models.py:168-194`.
    - Impact: completed orders cannot store/export the fiscal data promised by `PRODUCT.md`, and the irreversible boundary cannot revalidate ownership/current fiscal fields.

18. **[P2, confidence 9/10] Payment, webhook, refund, shipment, provider-failure, notification, and identity audit records are freely editable/deletable through Django admin.**
    - Code: `backend/commerce/admin.py:111-123` registers these models with default mutable `ModelAdmin`; only orders/reservations/inventory movements receive read-only protections at lines 45-108.
    - Impact: staff can rewrite signature validity, payment/refund state, manual-review reason/actor, diagnostics, and external IDs without append-only audit evidence.

19. **[P2, confidence 10/10] The committed report's Ruff claim is false for the reviewed commit.**
    - Evidence: `ruff check .` exits 1 at `backend/providers.py:133` (`UP038`: use `dict | list` in `isinstance`).
    - Impact: the brief's required lint verification is not green, despite `task-3-report.md` stating `All checks passed!`.

## OPTIONAL

1. **[P2, confidence 9/10] The Mercado Pago preference call occurs while cart/user/variant/order locks are held.** `backend/commerce/checkout.py:92-185` keeps the database transaction open across a provider call that can consume multiple 10-second attempts. Move provider I/O behind a durable idempotent state/outbox boundary so last-unit buyers are not blocked by provider latency.

2. **[P2, confidence 8/10] Andreani sync never removes or retires rows absent from the latest dataset.** `backend/locations/services.py:39-55` only `update_or_create`s. A withdrawn/renamed locality remains selectable forever; use generation markers or an atomic staged replacement.

3. **[P2, confidence 8/10] Package configuration lacks domain validation.** `backend/commerce/models.py:363-370` permits non-positive dimensions and `tare_weight_grams >= max_weight_grams`; admin exposes direct creation at `backend/commerce/admin.py:116`. Add model/database checks before staff configuration can make packing nonsensical.

4. **[P2, confidence 8/10] Periodic task queries and notification retries are unbounded.** `backend/commerce/tasks.py:23-32,52-68,71-104` scans all matching rows without batching/claiming, and notification attempts never reach a terminal failure state. Add indexed status/time fields, bounded batches with skip-locked claims, and a maximum-attempt policy.

## Verification performed

- `APP_ENV=test python -m pytest -q` -> **103 passed, 9 skipped**.
- Focused checkout/provider/API/OpenAPI tests -> **27 passed**.
- PostgreSQL evidence in the implementation report was inspected; the existing implementation test covers payment-versus-expiry, and the reservation service correctly locks the variant before calculating availability. It was not rerun in this pass.
- `python manage.py check` -> **pass**.
- `python manage.py spectacular --validate` -> **exit 0**.
- `python manage.py makemigrations --check --dry-run` -> **No changes detected**, with a warning because the local default PostgreSQL credentials could not authenticate.
- `git diff --check 41dfb3e 08c64275fd49d0ed1553baf406bcdadeea242b68` -> **pass**.
- `ruff check .` -> **fail (1 UP038)**.
- Focused live reproductions confirmed duplicate checkout reservations, invalid-webhook dedupe poisoning, non-final refund stock restoration, stale shipping fingerprints, non-exact CPA lookup, packing order dependence, MiCorreo payload mismatch, and HTML 500 from a missing staff action target.

## Final assessment

Task 3 should not be accepted or deployed against real providers in its current form. The reservation row-locking core is promising, but payment recovery, identity auditability, shipping quote binding, refund finality, and the complete MiCorreo integration need correction plus faithful boundary tests before the spec can pass.

---

## Fix Round 1 verdict — 2026-08-19

Fix reviewed: `5d7f070..ad9c5fd162b35293418db19510075d7f7ee044b6`

This round independently rechecked every REQUIRED finding above against the implementation, the new regression tests, `task-3-brief.md`, `PRODUCT.md`, and Correo Argentino's published [MiCorreo v1 contract](https://www.correoargentino.com.ar/MiCorreo/public/img/pag/apiMiCorreo.pdf). The regression work repairs most direct happy-path defects, but eight findings are only partial because failure recovery and public data/error contracts still have deploy-blocking gaps.

### Resolution of F1–F19

1. **F1 — RESOLVED.** `backend/commerce/shipping.py:104-235` now uses the documented QA/production base shape, HTTP Basic `POST /token` and response `token`, the required `/rates` customer/origin/destination/dimension payload and `rates` response, `POST /shipping/import`, and JSON-body `shippingId` on `GET /shipping/tracking`. `shipping.py:225-227` safely raises typed `not_supported` for the undocumented label route, mapped to HTTP 501 at `backend/api_views.py:775-798`. The faithful boundary assertions are at `backend/tests/test_task3_round1_regressions.py:71-194`. This matches the published v1 PDF pp. 1-2 and 8-18.

2. **F2 — PARTIAL (REQUIRED).** Normal and concurrent retries now have a client UUID and database uniqueness (`backend/commerce/serializers.py:109-115`, `backend/commerce/models.py:260-297`), and resume locks/reuses the original order (`backend/commerce/checkout.py:286-377`). However, preference creation still occurs inside the database transaction with provider idempotency generated on the transactional `PaymentTransaction` (`checkout.py:244-268`, similarly resume at `352-376`). If Mercado Pago succeeds and a later database step/commit fails, the order, transaction, and provider key roll back. A retry with the same checkout key generates a different provider key. A focused injected post-provider failure produced **2 provider calls, two different idempotency keys, 1 local order/transaction, and 1 orphan unbound identity attempt**. This violates recoverability/idempotency across the exact provider-success/DB-failure window; the new sequential/concurrency tests (`test_task3_round1_regressions.py:278-320`, `test_postgres_checkout.py:59-106`) do not assert it.

3. **F3 — RESOLVED.** `backend/commerce/checkout.py:53-87` binds price, active promotion/coupon-derived totals, product dimensions/weight, address, and final parcels; `checkout.py:101-108` rechecks it at confirmation. The regression varies price, coupon, address, and parcel fields at `backend/tests/test_task3_round1_regressions.py:218-275`.

4. **F4 — RESOLVED.** `backend/commerce/packing.py:57-72,94-141` canonicalizes rotations, unit tie-breaks, boxes, and free spaces. `backend/commerce/shipping.py:258-282` orders cart lines and persists box dimensions. The former equal-volume permutation now produces the same one-parcel result (`backend/tests/test_task3_round1_regressions.py:197-215`).

5. **F5 — RESOLVED.** `backend/api_views.py:1131-1175` passes signed query `data.id` and configured tolerance. `backend/commerce/payments.py:81-150` validates before accepting a duplicate and lets a valid delivery replace a prior rejected collision, then queues on commit. The poisoning reproduction is covered faithfully at `backend/tests/test_task3_round1_regressions.py:557-608`.

6. **F6 — PARTIAL (REQUIRED).** Provider failures now have bounded Celery autoretry and unexpected failures are returned to queued state (`backend/commerce/tasks.py:35-60`); a beat sweep exists (`tasks.py:63-81`, `backend/config/settings.py:274-277`). But claiming an event saves only `status` (`backend/commerce/payments.py:278-285`), so Django does **not** refresh the `auto_now` `updated_at` field. The sweep treats `updated_at` as the claim clock (`tasks.py:65-76`). A queued event older than five minutes was requeued by the sweep while its active worker was inside `fetch_payment`, producing a duplicate enqueue. The new test manually sets timestamps but never asserts that a real claim refreshes them (`backend/tests/test_task3_round1_regressions.py:612-655`). The implementation report's claim that the sweeper “refreshes their claim timestamp” is false.

7. **F7 — RESOLVED.** `backend/commerce/tasks.py:84-112` includes null-payment-ID pending rows and uses `find_payment(external_reference, preference_id)`; Mercado Pago implements server-side search at `backend/commerce/mercadopago.py:116-127`. The regression at `backend/tests/test_task3_round1_regressions.py:658-679` exercises the previously excluded row.

8. **F8 — RESOLVED.** Preferences now send independently returned order metadata (`backend/commerce/mercadopago.py:53-99`), and payment application requires it to equal the local public order UUID (`backend/commerce/payments.py:163-180`). Expired payments fail and refunded/chargeback states become `needs_attention` (`payments.py:252-265`). Amount, currency, configured collector, live mode, and external reference checks remain server-side.

9. **F9 — PARTIAL (REQUIRED).** Total refunds now send an empty body, wait for provider `approved`, lock the order, and reuse an existing same-key row before changing stock/status (`backend/commerce/payments.py:313-386`); pending-to-approved replay tests are faithful at `backend/tests/test_task3_round1_regressions.py:749-821`. The global idempotency-key race is not fully closed: two concurrent requests using one new key for **different orders** lock different orders, can both observe no `Refund` at line 316, then race the unique insert at lines 333-338. The loser gets an uncaught `IntegrityError`, not the intended stable `refund_idempotency_conflict`. The regression tests cover sequential same-order replay only.

10. **F10 — RESOLVED.** Checkout/direct validation require explicit affirmative consent (`backend/commerce/serializers.py:109-126`, `backend/commerce/checkout.py:133-136`, `backend/commerce/identity_service.py:18-29`), and timeout joins unavailable/not-configured in pending review (`identity_service.py:30-37`).

11. **F11 — RESOLVED.** Identity attempts are order-bound (`backend/commerce/models.py:346-378`, migration `0010_checkout_recovery_and_identity_binding.py:15-25`); manual approval requires a bound pending attempt and records actor/reason/time (`backend/commerce/identity_service.py:53-68`); resume queries only that order (`backend/commerce/checkout.py:286-291`). Explicit rejection cannot be overridden.

12. **F12 — RESOLVED.** `backend/locations/services.py:58-60` uses exact `cpa` for CPA8 and CP-only lookup for CP4. The two-row same-CP reproduction is now asserted at `backend/tests/test_task3_round1_regressions.py:465-481`.

13. **F13 — PARTIAL (REQUIRED).** Separate socket connect/read timeouts and complete disabled interfaces are present (`backend/providers.py:80-100`, `backend/commerce/provider_config.py:11-29`, `backend/commerce/shipping.py:86-101`). The transport still catches only `TimeoutError`/`OSError`; standard `http.client` protocol failures such as `RemoteDisconnected`, `BadStatusLine`, or `IncompleteRead` can escape without a typed provider error (`backend/providers.py:88-100`). Status classification also treats provider-declared request rejection 400 and MiCorreo's documented 402 validation errors as `unavailable`, because only 401/403/404/409/422 map to `ProviderRejected` (`providers.py:148-156`). This can yield unstable 500s for protocol failures and misleading retries/503s for bad customer payloads.

14. **F14 — PARTIAL (REQUIRED).** The order lock and eligibility checks close the original simultaneous-call race (`backend/commerce/shipping.py:323-342`), and deterministic per-parcel identifiers are used. Remote import still occurs before any durable local shipment/outbox row and inside the order transaction (`shipping.py:343-401`). If parcel 1 imports and parcel 2/provider or the final DB insert fails, no local row records the partial remote success; retry begins with parcel 1. MiCorreo documents an already-imported order as an error, so a partial multi-parcel import can remain unrecoverable despite deterministic IDs. The new SQLite/PostgreSQL tests cover simultaneous successful single-parcel calls, not provider-success/DB-failure or partial multi-parcel replay (`backend/tests/test_task3_round1_regressions.py:824-889`, `backend/tests/test_postgres_checkout.py:108-177`).

15. **F15 — PARTIAL (REQUIRED).** Missing staff targets, provider errors, refund domain failures, and unsupported labels now have stable mappings. Explicit SID rejection during **checkout** remains uncaught: `validate_identity()` raises `IdentityRejected` before the checkout transaction (`backend/commerce/checkout.py:147-156`), while `CheckoutView` catches only `CheckoutError` and `ProviderError` (`backend/api_views.py:1053-1073`). A focused API request returned **HTTP 500, `text/html`**. OpenAPI likewise omits that real outcome and documents only query `data.id`, not the required `x-signature` and `x-request-id` headers (`api_views.py:1136-1153`). The new tests cover typed invalid-response SID failure and missing staff rows, but not rejected checkout or those signature headers.

16. **F16 — PARTIAL (REQUIRED).** Production Compose now passes the missing controls, and startup validates SID mode/credentials, carrier credentials/base URL, webhook tolerance, and pricing numbers (`compose.prod.yaml:23-139`, `backend/config/settings.py:28-110`). Boolean controls are still parsed permissively rather than validated: `CORREO_ARGENTINO_ENABLED` accepts any typo as disabled (`settings.py:76`) and `MERCADOPAGO_LIVE_MODE` later accepts anything other than literal `true` as false. A focused call accepted `MERCADOPAGO_LIVE_MODE=definitely-not-a-boolean` and `CORREO_ARGENTINO_ENABLED=definitely-not-a-boolean`. Payment credentials may also be enabled with an empty collector ID (`settings.py:67-74`, `backend/commerce/provider_config.py:38-48`), silently disabling collector comparison. These are production fail-closed gaps.

17. **F17 — PARTIAL (REQUIRED).** Checkout now requires, locks, owns, snapshots, and resume-revalidates a billing profile (`backend/commerce/checkout.py:41-50,153-173,222-229,300-311`). However, the snapshot includes internal encrypted CUIT ciphertext and deterministic hash (`checkout.py:41-50`), and `OrderSerializer` returns the entire snapshot to the customer API (`backend/commerce/serializers.py:85-106`). A focused owner GET returned both non-empty `cuit_encrypted` and `cuit_hash`; only the masked CUIT should cross that API boundary under `PRODUCT.md:32`. The new tests inspect the model snapshot but do not inspect the public order payload.

18. **F18 — RESOLVED.** All named operational/audit models are registered with `AppendOnlyAdmin`, whose fields are read-only and whose add/change/delete permissions are false (`backend/commerce/admin.py:45-60,133-141`). The regression checks each registration at `backend/tests/test_task3_round1_regressions.py:959-988`.

19. **F19 — RESOLVED.** `ruff check .` now exits 0 with “All checks passed!”.

### Fix Round 1 counts and verdict

- **Resolved:** 11 (`F1`, `F3`, `F4`, `F5`, `F7`, `F8`, `F10`, `F11`, `F12`, `F18`, `F19`)
- **Partial:** 8 (`F2`, `F6`, `F9`, `F13`, `F14`, `F15`, `F16`, `F17`)
- **Unresolved:** 0
- **Remaining REQUIRED issues:** 8
- **SPEC COMPLIANCE: FAIL**
- **CODE QUALITY: FAIL**

The implementation should not be accepted yet. Normal-flow coverage is substantially improved, MiCorreo v1 is now faithful (with a safe typed 501 for labels), and the original quote/packing/identity/order-binding defects are repaired. Acceptance remains blocked by durable provider/DB idempotency, webhook claim safety, multi-parcel shipment recovery, stable rejected-checkout errors, strict startup configuration, typed HTTP failures, refund collision handling, and masked fiscal API output.

### Fix Round 1 verification performed

- `APP_ENV=test python -m pytest -q` -> **128 passed, 11 skipped**.
- Focused Task 3/provider/API/OpenAPI suites -> **52 passed**.
- PostgreSQL-only tests were inspected but not rerun locally because the configured PostgreSQL credentials were unavailable; the implementation report records 12 passing cases, but neither new PostgreSQL case covers provider-success/DB-failure recovery.
- `ruff check .` -> **pass**.
- `python manage.py check` -> **pass**.
- `python manage.py spectacular --validate --file NUL` -> **exit 0**.
- `python manage.py makemigrations --check --dry-run` -> **No changes detected**, with the expected local PostgreSQL authentication warning.
- `git diff --check 5d7f070 ad9c5fd` -> **pass**.
- Focused live reproductions confirmed: distinct provider keys after checkout rollback; orphan unbound identity audit row; an active stale webhook claim swept/requeued; HTML 500 on explicit SID checkout rejection; public fiscal ciphertext/hash exposure; and permissive invalid production booleans.
