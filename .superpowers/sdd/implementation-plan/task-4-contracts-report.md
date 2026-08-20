# Task 4 backend and infrastructure contract repair report

## Outcome

The Task 4 storefront backend and media topology are repaired. The versioned API now publishes
the customer identity write path, explicit address confirmation transition, complete server-side
catalog/search envelope, authoritative cart-line amounts and change notices, and safe order
fulfillment detail required by the storefront. Uploaded catalog and landing media is emitted as a
same-origin path and served from a persistent shared volume by Caddy in development and production.

No frontend files were changed by this backend/infra work. The Impeccable detector was not run and
`DESIGN.md` was not created.

## Final public contract

### Registration and customer profile

- `POST /api/v1/auth/register/` accepts `email`, `password`, `consent_version`, `first_name`,
  `last_name`, and `phone`. The three profile fields are optional at the low-level API boundary for
  backwards compatibility with established clients, but the Task 4 storefront requires them in its
  registration form. Supplied names are trimmed, nonblank, and at most 120 characters. A supplied
  phone is trimmed, at most 32 characters, contains 6 through 15 digits, and accepts only digits,
  spaces, `+`, `-`, `.`, `/`, and parentheses.
- `PATCH /api/v1/customers/me/` requires an authenticated, verified session and a valid CSRF token.
  The request accepts any subset of `first_name`, `last_name`, `phone`, and `dni`. DNI punctuation is
  removed and the result must contain exactly eight digits. The update is atomic and delegates DNI
  storage to `CustomerProfile.set_dni`.
- Both successful operations return the existing customer shape:
  `{id,email,email_verified_at,profile:{first_name,last_name,phone},masked_dni,masked_cuit}`.
  Plaintext DNI, hashes, ciphertext, and internal identity fields are never serialized.

### Address confirmation

- `POST /api/v1/addresses/{id}/confirm/` requires an authenticated, verified, CSRF-valid owner.
- Request: `{latitude, longitude, address_choice}` where coordinates are decimal values with seven
  decimal places and `address_choice` is `written` or `reverse`.
- Confirmation only accepts the coordinates currently persisted by a forward or reverse geocode,
  within two metres. `written` is valid after forward geocoding and `reverse` after reverse lookup.
  This supports an unchanged/near initial pin and the second confirmation after a greater-than-150m
  reverse lookup.
- Success returns the full address with `needs_review=false` and `reviewed_at` set. The safe
  `geocode_summary.confirmation` audit contains only the choice and timestamp.
- Stable `409` codes are `address_not_geocoded`, `address_coordinates_missing`,
  `address_coordinates_changed`, and `address_choice_mismatch`; non-owner records return `404`.
- Floor, apartment, reference, and notes are never passed to GeoRef.

### Catalog, search, and media

- `GET /api/v1/products/` and `GET /api/v1/search/` return
  `{count,next,previous,results,facets}`. Search returns an empty result without `q` or `search`;
  products supports query-free browsing.
- Supported query parameters are `q`, `search`, descendant-aware `category`, `brand` (one or
  comma-separated slugs), `min_price`, `max_price`, `availability=in_stock|out_of_stock`,
  `offer=true|false`, dynamic `attribute_<slug>`, `ordering`, `page`, and `page_size` (1-100,
  default 24). Ordering is one of `relevance`, `newest`, `price_asc`, `price_desc`, and
  `discount_desc`.
- Dynamic attributes are parsed according to their declared text/integer/decimal/boolean/option
  type. All variant-level filters must match one real variant; separate variants cannot jointly
  satisfy one filter request.
- PostgreSQL uses Spanish full-text rank plus `pg_trgm` name similarity. SQLite uses a deterministic
  `icontains` fallback for local tests.
- Products expose category, safe brand, total available stock, minimum effective price, offer state,
  active variants, and media. Variants expose available stock, filterable typed attributes, and
  `{list_price,effective_price,discount_amount,discount_percentage,on_offer}`. Cost is absent.
- Facets contain a recursive category tree with counts, brands, effective price bounds,
  availability/offer counts, and filterable typed attribute values for the filtered result scope.
- Catalog `media[].file` and landing desktop/mobile image URLs are always relative `/media/...`
  paths; request or container hostnames are never embedded.

### Cart

- Cart totals remain authoritative decimal strings.
- Each line exposes `unit_price`, `line_subtotal`, `line_discount`, `line_total`, `availability`,
  `available_stock`, and a stable `notices` array in addition to its identifiers and quantity.
- Availability is `available`, `insufficient_stock`, or `unavailable`. Notices contain
  `{code,previous,current}` with code `price_changed` or `stock_changed`. Initial price/stock
  snapshots are migration-safe and nullable for existing lines.

### Order detail and pickup settings

- Owner-only order detail adds a maximum of 50 public timeline entries shaped
  `{status,label,occurred_at}`. Only order creation and identity/payment/fulfillment transitions are
  mapped; arbitrary audit data and staff diagnostics are ignored.
- `shipment` is null or `{carrier,tracking_number,status,updated_at}`. Provider IDs, summaries,
  label URLs, and secrets are absent.
- `pickup_information` is null for shipping and `{enabled,label,address,hours}` for pickup.
  `SiteSettings` stores those four values with safe data defaults, and storefront home settings
  publishes the same configuration.

### Media topology

- Django uses configurable `MEDIA_ROOT`; both Compose topologies set it to `/app/media`.
- A persistent `media_data` volume is writable by the backend and mounted read-only at
  `/srv/media` in Caddy.
- Caddy handles `/media/*` directly with its file server before the frontend fallback in development
  and production.

## Migrations

- Catalog migration `0003` enables `pg_trgm` and adds `Product.created_at` with both application and
  database defaults, preserving historical-model inserts and existing rows.
- Commerce migration `0012` adds nullable cart-line price and stock observation snapshots.
- Landing migration `0003` adds pickup settings with non-destructive defaults.

## TDD evidence

- First RED: `tests/test_task4_storefront_contracts.py` produced 11 failures out of 11 for the
  missing registration/profile, address, media, catalog, cart, order, and OpenAPI contracts.
- Infra RED: rendered development and production Compose tests failed 2 out of 2 because
  `media_data` did not exist.
- Compatibility RED: the first full suite found two legacy registration tests and one historical
  migration test. The API kept legacy registration compatibility and the creation timestamp gained
  a database-side default.
- Edge RED: explicit tests demonstrated cross-variant price-range false positives, confirmation of
  non-geocoded coordinates, and decimal dynamic-attribute mismatches before the minimal fixes.
- Final focused GREEN: Task 4 contracts and rendered media topology pass, including owner scoping,
  CSRF, all four address confirmation codes, typed query errors, masked identity responses, and
  OpenAPI paths/parameters.
- A cookie-aware integration test covers registration, six-digit verification, login CSRF rotation,
  masked DNI update, fiscal profile creation, provider-isolated geocoding, address confirmation,
  authoritative cart pricing, and safe pending-identity checkout in one journey.

## Verification

- `APP_ENV=test python -m pytest -q`: **162 passed, 13 skipped**.
- PostgreSQL Compose run of `test_postgres_round1.py`, `test_postgres_inventory.py`,
  `test_postgres_checkout.py`, and `test_task4_storefront_contracts.py`: **27 passed**.
- `python -m ruff check .`: **pass**.
- `APP_ENV=test python manage.py check`: **pass**.
- `APP_ENV=test python manage.py makemigrations --check --dry-run`: **no changes detected**.
- `APP_ENV=test python manage.py spectacular --validate`: **pass**.
- `tests/test_media_topology.py`: **2 passed**, using fully rendered dev and production Compose.
- Caddy 2.10 `caddy validate` against both Caddyfiles: **valid configuration**.

The 13 SQLite skips are the pre-existing PostgreSQL/provider-gated tests; the PostgreSQL-relevant
paths were run separately and passed. No live SID, carrier, or payment credentials were used.
