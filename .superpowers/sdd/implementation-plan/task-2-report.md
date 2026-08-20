# Task 2 report: Django commerce domain and REST API

## Summary

Implemented the Task 2 backend commerce foundation on `feat/ecommerce-foundation` without adding live provider, Mercado Pago, Correo Argentino, geocoding, identity-provider, or webhook orchestration. The implementation preserves the Task 1 production environment validation, WhiteNoise manifest storage, Compose topology, and frontend.

The domain is split into five Django bounded apps:

- `accounts`: email-only custom user, customer/profile/fiscal data, consent, verification challenges, and protected DNI/CUIT storage.
- `catalog`: category tree, brands, typed/filterable attributes, products, media, and sellable SKU variants.
- `commerce`: promotions, coupons, carts, inventory movements/reservations, order snapshots, and audit events.
- `locations`: owner-scoped Argentine address records with raw/normalized, postal, map, geocoding, and review fields.
- `landing`: staff-managed site settings, hero/promotion slides, collections, and popup content.

## Architecture, models, and services

### Accounts and sensitive data

- `accounts.User` is the first-migration auth model, uses unique email as `USERNAME_FIELD`, and has no username field.
- `Profile`, `CustomerProfile`, and `BillingProfile` separate general, customer-consent, and fiscal concerns.
- `EmailVerificationChallenge` accepts exactly six digits, stores only a Django password hash, expires after 15 minutes, and supports one-time consumption.
- DNI/CUIT values are encrypted using Fernet with a key derived from `PERSONAL_DATA_ENCRYPTION_KEY`; deterministic HMAC-SHA256 hashes support safe equality lookup; admin/API presentation is masked.
- Production startup now rejects a missing, short, or development-placeholder personal-data encryption key. Development and production Compose pass the setting explicitly; the example configuration contains only a development placeholder.

### Catalog and landing content

- Category ancestry is validated against cycles and a maximum depth of five.
- `AttributeDefinition`, `AttributeOption`, and `AttributeValue` support text, integer, decimal, boolean, and enumerated option values with filterability metadata.
- Sellable products cannot be saved without at least one variant. Variant SKUs are unique and store price, staff/admin-only cost, packaged grams, dimensions, stock, and derived cubic-centimeter volume.
- Public serializers deliberately omit cost, including for authenticated/staff requests to public storefront routes.
- Landing content models include enabled/order/schedule fields, desktop/mobile files, alt text, CTAs, focal coordinates, and safe heights for mobile/tablet/desktop.

### Commerce transitions

- Automatic fixed/percentage promotion rules target products and categories. `best_automatic_discount` picks one best line discount and never stacks automatic rules.
- Carts allow one coupon. Non-combinable is the default; a non-combinable coupon competes with automatic discounts and only the better result applies. Combinable coupons explicitly add to automatic savings.
- Cart totals are server-calculated from current variant prices and returned as two-decimal strings. Client price fields are ignored.
- Anonymous carts use Django-signed opaque tokens. Authenticated carts are owner-bound, and `merge_carts` merges quantities/coupon state during login.
- `create_reservation` runs in `transaction.atomic`, locks the variant with `select_for_update`, computes availability as on-hand minus active unexpired reservations, and rejects overselling. Default expiry is 20 minutes.
- Reservation consumption and release lock the reservation and are idempotent. Inventory movements preserve reservation, sale, and release audit history.
- `create_pending_identity_order` snapshots customer, address, fiscal, item, SKU, price, discounts, totals, coupon code, and fulfillment method. Identity, payment, and fulfillment states are independent. A `pending_identity` order creates no reservation.
- Business state transitions are service functions; no model-signal orchestration was introduced.

## REST API (`/api/v1`)

- Public storefront: `storefront/home/`, `categories/`, `products/`, `products/<slug>/`, and `search/`.
- Session/auth: `auth/csrf/`, `auth/register/`, `auth/email-verify/`, `auth/login/`, `auth/logout/`, `customers/me/`, and owner-scoped `billing-profiles/`.
- Cart: `cart/` supports GET/POST/PATCH/DELETE with signed anonymous ownership or authenticated ownership and authoritative totals.
- Locations: owner-scoped `addresses/` CRUD.
- Provider boundaries: `identity/status/` returns `{"status": "not_configured"}`; `checkout/` returns HTTP 503 with `{"code": "not_configured"}`.
- Orders: read-only owner-scoped list/detail, with detail lookup by public UUID.
- OpenAPI: `schema/` plus Swagger UI at `schema/docs/`, generated through drf-spectacular.

## Admin and staff permissions

- Admin registrations include useful list columns, search, filters, read-only audit/snapshot fields, and product/order inlines.
- Data migration `commerce.0002_staff_permission_groups` creates `Owner`, `Catalog`, `Orders/Logistics`, and `Content` with bounded model permissions. Owner receives all permissions for the five Task 2 apps.
- Provider credentials and secrets are not stored in domain models.

## Migrations and deterministic data

- Initial migrations: `accounts.0001`, `catalog.0001`, `commerce.0001`, `locations.0001`, and `landing.0001`.
- Permission groups: `commerce.0002_staff_permission_groups`.
- Coupon order snapshot: `commerce.0003_order_coupon_code_snapshot`.
- `seed_synthetic_data` is idempotent and creates only explicitly labeled synthetic catalog/landing records. It contains no testimonials, commercial metrics, customer claims, or real identities.
- Hash-locked dependency inputs and locks were updated consistently for `cryptography==46.0.3` and `drf-spectacular==0.29.0`.

## TDD red/green evidence

Tests were written and observed failing before each associated behavior was implemented. Representative recorded RED results:

- Custom user: expected `USERNAME_FIELD == "email"`, received `"username"` (`1 failed`).
- Category/variant behavior: missing `catalog.models` (`2 failed`).
- Verification and protected identifiers: missing challenge/profile models (`2 failed`).
- Promotions, cart, inventory, snapshots, and coupon policy: missing commerce models/services (`7 failed`).
- Public cost, cart authority, address ownership, provider boundaries, and schema: missing routes/models (`5 failed`; the order ownership test was subsequently strengthened to assert owner 200 before non-owner 404).
- Sellable invariant: product without variants did not raise (`1 failed`).
- Available stock: missing `available_stock` (`1 failed`).
- Staff groups: no groups existed (`1 failed`).
- Production personal-data key: placeholder was not rejected (`1 failed`).
- Coupon order snapshot: missing `coupon_code_snapshot` (`1 failed`).

Each was followed by a targeted GREEN run. The final local suite result is `31 passed, 1 skipped`; the single SQLite skip is the PostgreSQL-only concurrency test, which passed separately against Compose PostgreSQL.

## Commands and results

- `APP_ENV=test pytest -q` — `31 passed, 1 skipped in 5.92s`.
- `docker compose run --rm -e APP_ENV=test -e USE_POSTGRES_TEST_DB=true backend pytest tests/test_postgres_inventory.py -q` — `1 passed in 13.16s` against PostgreSQL 17.
- `ruff check .` — `All checks passed!`.
- `APP_ENV=test python manage.py check` — `System check identified no issues (0 silenced)`.
- `APP_ENV=test python manage.py makemigrations --check --dry-run` — `No changes detected` (the command also emitted a non-fatal local PostgreSQL authentication warning while checking migration history because no matching host credentials were supplied).
- `APP_ENV=test python manage.py spectacular --file openapi-schema.yml --validate` — exit 0, zero schema warnings/errors; generated verification artifact removed afterward.
- `docker build --target production ...` — the WhiteNoise production build stage completed `collectstatic` (`163 static files copied`, `426 post-processed`). The later image ownership/export layer was stopped on coordinator direction and is not claimed as a complete production-image build.
- `docker compose down` — temporary PostgreSQL/Redis containers and network removed; the named PostgreSQL development volume was preserved.

## Commits

- Implementation: `2a55d93 feat(backend): add commerce domain and REST API`
- Report: committed separately after this report was written.

## Concerns

- No Task 3 provider workflows are present by design; identity and checkout boundaries explicitly report `not_configured`.
- A complete production image export was not used as completion evidence because the final ownership layer was stopped on coordinator direction. Its required WhiteNoise `collectstatic` stage did complete successfully.
- The PostgreSQL concurrency contract was verified through Compose and is not inferred from SQLite.

---

## Fix Round 1

### Summary

Resolved every required review finding F1-F17 and the straightforward optional singleton finding F19 without adding Task 3 providers or frontend work. The fix commit is `4e8709d fix(backend): harden commerce domain invariants`.

The production image no longer inherits the build-time personal-data key. Login/logout session mutations enforce CSRF; verified email is a central permission at PII, identity, order, and checkout boundaries; verification challenges now have atomic one-time consumption, bounded attempts, lockout, and email/IP throttling. Registration canonicalizes email, validates passwords and consent, and returns a stable conflict response. DNI/CUIT input and admin replacement paths validate before encryption and expose only resilient masks.

Catalog invariants now use explicit transactional services for category reparenting and product/variant state transitions. Direct reparent, bulk parent update, and unsafe last-active-variant deactivation/deletion are blocked. Typed attributes require exactly one declared storage type and same-definition options. Product variants, discounts, schedules, money, weight, and dimensions have model validators and database constraints.

Commerce now has one authenticated cart per user, atomic line adds, stable-order cart locking/merge, expiry-safe reservation transitions, coherent locked order pricing, deterministic cent allocation, and a persisted item/order reconciliation invariant. Order snapshots, items, audit events, and inventory movements are immutable; status changes go through an atomic audited service; logistics permissions and admin mutation paths are restricted.

Landing content now uses validated image fields, safe CTA schemes, focal and height bounds, ordered schedules, positive unique product IDs, explicit serializers, stable media URLs, and a complete typed home response. `SiteSettings` is enforced as a single keyed record and the admin cannot add a second record or delete it. OpenAPI operations use dedicated request/response schemas and explicit success/error status codes. Production cookies, proxy TLS handling, HTTPS redirect, and HSTS pass Django's deploy checks.

### Architecture, models, and API

- `accounts.services.consume_email_verification_challenge` owns the locked verification transition; `accounts.permissions.IsVerifiedEmail` owns the protected boundary; throttles hash canonical email plus client IP.
- `catalog.services.move_category`, `activate_product`, `set_variant_active`, and `delete_variant` own tree and sellability transitions. Queryset/model guards prevent ordinary bypasses.
- `commerce.services` owns atomic cart creation/add/merge, reservation transitions, one-timestamp priced-line snapshots, coupon allocation, order creation, and audited status transitions. No model signals were introduced.
- Append-only commerce records reject direct update/delete in models/querysets and are read-only/non-deletable in admin. The logistics group retains view access but loses unsafe default mutation permissions.
- Public catalog serializers include active variants only and still omit `cost`; product and cart routes require active, sellable product state.
- Landing serializers explicitly cover settings, hero/promotion slides, collections, and popups, including media URLs, body/product IDs, focal coordinates, safe heights, CTA, order, and schedules.
- Auth, cart, identity, checkout, and other `/api/v1` operations publish semantically dedicated OpenAPI request/response/status contracts; the schema contract has a structural regression test.

### Migrations and dependencies

- `accounts.0002` adds verification attempts/lockout and case-insensitive email uniqueness; `accounts.0003` preserves inherited Django user metadata.
- `catalog.0002` adds product-variant validators/database constraints and exact-one attribute storage.
- `commerce.0004` adds discount/schedule constraints, `0005` adds unique authenticated carts and positive cart quantities, and `0006` removes unsafe logistics mutation permissions.
- `landing.0002` migrates image, CTA, focal, and responsive-height validation fields.
- `Pillow==12.1.0` was added for Django `ImageField`. Both production and development locks were regenerated with pip-tools and hashes; both locks installed successfully during the development/production Docker builds with `--require-hashes`.
- Fresh PostgreSQL migration application completed through `sessions.0001`; `migrate --check` succeeded and `makemigrations --check --dry-run` returned `No changes detected`.

### TDD red/green evidence

Round 1 behavior was developed through focused failing tests before implementation:

- Security/auth initial RED: `11 failed, 1 passed`; focused GREEN: `12 passed` (later expanded with masked-admin and deploy tests).
- Catalog/CMS initial RED: `10 failed, 4 passed`; focused GREEN: `14 passed` (later expanded to 15 with complete settings/product-ID validation).
- Commerce initial RED: `7 failed, 1 passed`; focused GREEN: `8 passed`; append-only/queryset hardening additionally recorded `3 failed` then `3 passed`.
- OpenAPI semantic RED: registration exposed only the success response and incorrect shared schemas; GREEN: `1 passed` over all expected `/api/v1` paths and dedicated auth/cart/checkout contracts.
- Full-suite regression RED after adding the verified-email/permission boundary: `4 failed, 64 passed, 5 deselected`; fixtures/expectations were corrected to the new security contract, then the suite passed.
- PostgreSQL RED: the first order/cart race run found Django/PostgreSQL's `FOR UPDATE cannot be applied to the nullable side of an outer join` (`1 failed, 4 passed`). Cart and coupon locks were separated; the focused regression passed, followed by the complete marked run.

Final GREEN evidence:

- `APP_ENV=test pytest -q` — `69 passed, 7 skipped in 18.32s`; every skip is explicitly PostgreSQL-marked.
- `docker compose run --rm -e APP_ENV=test -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql` — `7 passed, 69 deselected in 36.50s` against PostgreSQL 17. This covers oversell protection, one-time challenge consumption, lossless concurrent failed attempts, unique cart creation, concurrent adds, simultaneous merges, coherent order/cart snapshots, and expired reservation reuse.
- `APP_ENV=test pytest -q tests/test_catalog_cms_round1.py tests/test_openapi_semantics.py` — `15 passed`; includes the semantic schema gate and complete public CMS contract.

### Verification commands and results

- `ruff check backend` — `All checks passed!`.
- `git diff --check` — passed (only Git's Windows line-ending notices were printed).
- `APP_ENV=test python manage.py check` — no system-check issues.
- Production `python manage.py check --deploy --fail-level WARNING` with non-placeholder runtime values — no issues; also enforced by `test_production_settings_pass_django_deploy_checks`.
- Compose migration apply/check and `makemigrations --check --dry-run` — all migrations applied, no unapplied or ungenerated changes.
- `docker build --target production -t mycdigitalizaciones-backend-round1 backend` — completed, including `163 static files copied` and `426 post-processed` through WhiteNoise.
- `docker image inspect ... .Config.Env` — final image contains only Python/pip runtime environment entries; no `APP_ENV`, signing key, database password, site value, or personal-data key is inherited.
- Starting that final image in production with all required values except `PERSONAL_DATA_ENCRYPTION_KEY` exits `1` with `ImproperlyConfigured: PERSONAL_DATA_ENCRYPTION_KEY must be a non-placeholder production value`, proving runtime fail-fast.

### Concerns

- F18 key rotation remains intentionally unimplemented because it was optional and outside this fix-round scope. Current encrypted/hash data still requires an operationally coordinated key migration if the personal-data key changes.
- Provider/checkout/identity orchestration remains explicitly `not_configured` for Task 3; no provider calls were added.

---

## Fix Round 2

### Summary

Resolved only the required partial findings F1, F6, F7, F9, F12, F14, and F16. No provider orchestration, frontend work, F18 key rotation, or F19 changes were added.

- F1: the production Docker recipe no longer contains build-time signing, database, host, or personal-data literals. Static collection runs under the non-production test context; every previously committed build literal is permanently rejected by the production runtime validator, and the final image inherits none of them.
- F6: `AttributeValue` manager/queryset bulk create, bulk update, and update paths cannot bypass exact declared-type or same-definition option validation.
- F7: product queryset activation is blocked, model activation requires an active variant, and the explicit activation service is the only supported transition path.
- F9: cart lock acquisition is ordered by primary key. A deterministic, upgrade-safe data migration reconciles historical duplicate authenticated carts before adding uniqueness: the lowest-PK cart survives, line quantities are summed, and the target coupon wins or otherwise the first non-null coupon by cart PK is retained.
- F12: order update/delete and reservation lifecycle update/delete paths are guarded at queryset and instance level. Scoped internal transition capabilities are cleared even when service calls return the transitioned objects.
- F14: historical case-only duplicate emails are reconciled before the `Lower(email)` constraint: the lowest-PK account retains the canonical email, deterministic inactive aliases preserve every conflicting row, and registration maps only an actual email unique conflict to HTTP 409.
- F16: every protected customer, billing, address, order, identity, and checkout read/CRUD operation documents its real 400/401/403/404/409/503 responses with safe error components and endpoint-appropriate success schemas.

### Architecture and migrations

- Catalog and commerce invariants remain explicit service transitions with guarded model/queryset escape hatches; no model-signal orchestration was introduced.
- `accounts.0002` now canonicalizes and deterministically reconciles historical emails before creating case-insensitive uniqueness.
- `commerce.0005` now reconciles duplicate carts/lines/coupons before uniqueness. The migration is deliberately non-atomic so PostgreSQL commits deferred FK trigger events from line reconciliation before building the unique index.
- Historical `MigrationExecutor` tests migrate real pre-fix states forward and restore the latest schema. PostgreSQL fresh-test-database application also verifies the full graph from zero.
- No dependency input or hash lock changed in this round. Production image installation continued to use the existing `pip --require-hashes` layer.

### TDD red/green evidence

- Domain bypass regressions (F1/F6/F7/F12) initially produced `5 failed`; the same focused file then passed `5 passed`.
- Scoped service-capability cleanup produced `2 failed`, followed by `2 passed` after transition flags were made exception-safe and one-shot.
- Historical migration/security regressions produced `3 failed`: both new uniqueness constraints rejected historical duplicates and an unrelated registration `IntegrityError` was incorrectly returned as an email conflict. The focused set then passed `3 passed`.
- OpenAPI semantics initially failed because protected customer operations omitted documented errors (`1 failed`); the complete endpoint matrix then passed (`1 passed`).
- The strengthened Docker regression first found all five sensitive assignments still present (`1 failed`); after removing them from the recipe and retaining explicit historical-literal checks, it passed (`1 passed`).
- PostgreSQL exposed `cannot CREATE INDEX ... because it has pending trigger events` in the cart upgrade probe. Making the reconciliation/constraint migration non-atomic produced `1 passed` for that same historical upgrade.

### Final commands and results

- `APP_ENV=test python -m pytest -q` — `77 passed, 7 skipped in 27.19s`.
- `docker compose run --rm -e APP_ENV=test -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql` — `9 passed, 75 deselected in 46.65s` against PostgreSQL 17. This includes the two historical upgrade probes plus the existing concurrency/locking matrix.
- `python -m ruff check .` — `All checks passed!`.
- `APP_ENV=test python manage.py check` — no issues.
- Production `python manage.py check --deploy` with non-placeholder runtime settings — no issues.
- `APP_ENV=test python manage.py makemigrations --check --dry-run` — `No changes detected`; a non-fatal host PostgreSQL authentication warning was emitted only while Django attempted to inspect local migration history. Fresh PostgreSQL migration application is covered by the marked suite.
- Compose-backed `python manage.py makemigrations --check --dry-run` — `No changes detected` with the PostgreSQL service healthy.
- `APP_ENV=test python manage.py spectacular --file <temporary> --validate` — exit 0 with no warnings; the temporary schema file was removed.
- `docker build --target production -t mycdigitalizaciones-backend-task2-round2 backend` — completed, including hash-locked dependencies and WhiteNoise (`163 static files copied`, `426 post-processed`).
- `docker image inspect ... .Config.Env` — only base Python/pip environment values; no application secret, host, or build literal.
- Final-image startup with the previously committed PII literal exited 1 with `ImproperlyConfigured: PERSONAL_DATA_ENCRYPTION_KEY must be a non-placeholder production value`.

### Concerns

- F18 key rotation remains intentionally out of scope and unimplemented, as required for this round.
- Task 3 provider orchestration remains explicitly absent.

---

## Fix Round 3 — F16 only

### Summary

Aligned the generated OpenAPI contract exactly with the configured DRF `SessionAuthentication` runtime. Protected customer, billing, address, order, identity, and checkout operations no longer advertise an unreachable `401`; their exact response sets use the real unauthenticated/unverified `403` behavior. Auth and cart operations now also have exact status matrices, including cart-token `404` responses and real cart request-validation `400` responses.

Serializer validation errors are documented as an object whose arbitrary field names (including `non_field_errors`) map to lists of strings. Operations that can also return business-domain failures use a non-overlapping `oneOf` with a required, closed `code`/`detail` object. Domain failures for verification, login, cart lookup/update, and coupons now return that stable shape. CSRF failures remain their real HTML 403 response and are documented without a false JSON body schema.

Cart POST/PATCH/DELETE now execute their already-published dedicated request serializers before reading values. This makes malformed IDs/quantities deterministic 400 field-error maps instead of uncaught conversion errors, without changing domain models, migrations, providers, or frontend code.

### Semantic contract coverage

- Exact response-key equality is asserted for every customer, billing CRUD, address CRUD, order read, identity, checkout, cart, and auth operation; subset assertions can no longer hide spurious statuses.
- Real unauthenticated requests prove the session-only protected boundary emits 403 and validate each JSON body against the documented response schema.
- Real success/validation/not-found/provider responses cover customer, billing, addresses, orders, identity, checkout, cart, registration, email verification, login, and CSRF acquisition.
- Runtime payload validation uses the generated OpenAPI document itself, resolving components and translating OpenAPI 3 `nullable` to equivalent JSON Schema solely inside the test validator.
- Serializer validation probes include field errors and multiple-field/non-field-compatible maps; domain probes assert exact stable codes/details for invalid verification challenges, credentials, variants, and coupons.
- Enforced-CSRF login verifies the real HTML 403 matches a bodyless documented response rather than an advertised JSON error.

### TDD red/green evidence

- Initial exact-status/runtime-schema tests: `2 failed`; they exposed the extra protected `401` and validation maps being documented as string-valued `Error` objects.
- After the first annotation pass, the runtime-schema test still failed because invalid credentials returned a flat list rather than either documented error shape.
- Cart request validation regression failed with an uncaught `ValueError` for a non-integer variant ID and showed PATCH/DELETE missing their real 400 contracts. Executing the dedicated serializers made those paths deterministic validation responses.
- The first mixed validation/domain `oneOf` failed because the permissive legacy `Error` component overlapped with every validation map. A required, closed `code`/`detail` branch made the alternatives unambiguous.
- Invalid coupon coverage then reproduced the previously uncaught Django `ValidationError`; the API boundary now maps it to `{"code":"invalid_coupon","detail":"Coupon is invalid"}`.
- A missing cart target initially returned the domain `unknown_variant` response; the cart request serializer now emits the documented `non_field_errors` list requiring either `variant_id` or `coupon`.
- Final focused run: `2 passed in 3.58s`.

### Commands and results

- `APP_ENV=test pytest -q tests/test_openapi_semantics.py` — `2 passed in 3.58s`.
- `APP_ENV=test python -m pytest -q` — `78 passed, 7 skipped in 22.74s`; skips remain PostgreSQL-marked tests unaffected by this F16-only round.
- `APP_ENV=test python manage.py spectacular --file <temporary> --validate` — exit 0 with no warnings; the temporary artifact was removed.
- `python -m ruff check .` — `All checks passed!` after applying the reported import/line formatting corrections.
- `git diff --check` — passed with only the existing Windows line-ending notices.

### Concerns

- None within the F16 scope. No model, migration, dependency, provider, or frontend changes were made.
