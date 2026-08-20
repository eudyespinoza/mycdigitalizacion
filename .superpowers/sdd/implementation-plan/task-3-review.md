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
