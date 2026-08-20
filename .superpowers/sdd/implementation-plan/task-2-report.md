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
