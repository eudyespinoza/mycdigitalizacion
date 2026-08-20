# Task 5A Admin, CMS and Media Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a branded, least-privilege Django staff panel with safe CMS/catalog/order operations, audited spreadsheet exports, and hardened image handling.

**Architecture:** Keep Django Admin as the permission authority and add small domain services for role synchronization, guarded order operations, imports/exports, and image processing. Admin classes expose those services but never write sensitive states directly. CMS behavior remains model-validated and is serialized through the existing storefront home contract.

**Tech Stack:** Django 5.2, DRF, Pillow 12, Python csv, openpyxl 3.1, pytest, PostgreSQL/SQLite.

**Spec:** `.superpowers/sdd/implementation-plan/task-5-brief.md`

## Global Constraints

- Backend and admin assets only; do not edit frontend, infrastructure, or Compose.
- Strict RED-GREEN TDD for every behavior change.
- Existing domain services remain authoritative for sensitive transitions.
- Public serializers never expose cost, plaintext fiscal identifiers, hashes, ciphertext, provider secrets, or staff diagnostics.
- No detector and no `DESIGN.md`.

---

### Task 1: Admin identity, authentication hardening and roles

**Files:**
- Create: `backend/config/admin_security.py`
- Create: `backend/config/admin_roles.py`
- Create: `backend/accounts/management/commands/setup_admin_roles.py`
- Create: `backend/templates/admin/base_site.html`
- Create: `backend/templates/admin/index.html`
- Create: `backend/landing/static/admin/css/mycdigitalizacion.css`
- Create: `backend/landing/static/admin/img/mycdigitalizacion-mark.svg`
- Modify: `backend/config/settings.py`, `backend/config/urls.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- Produces `sync_admin_roles() -> dict[str, int]`, `RateLimitedAdminAuthenticationForm`, and `AdminTwoFactorGateMiddleware`.
- Role names are exactly Owner, Catalog, Orders/Logistics, and Content.

- [x] Write tests that log into the real admin, exhaust a bounded failed-login window, exercise the opt-in 2FA session gate, render branded responsive templates, and compare role permissions to literal least-privilege sets.
- [x] Run the focused tests and record the missing-branding/rate-limit/role-command failures.
- [x] Implement branding, accessible CSS, safe cache-backed throttling, opt-in 2FA gate, exact role synchronization, and the idempotent management command.
- [x] Re-run the focused tests until green.

### Task 2: CMS scheduling, presentation controls and admin workflow

**Files:**
- Modify: `backend/landing/models.py`, `backend/landing/admin.py`, `backend/landing/serializers.py`
- Create: `backend/landing/migrations/0005_task5a_content_controls.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- Hero/promotion API adds `interval_ms` and `pause_on_reduced_motion`.
- Popup API adds `frequency`, `display_delay_ms`, and `dismissible`.
- Admin provides `duplicate_selected`, editable ordering, image thumbnails, and public-preview links.

- [x] Write tests for conditional alt text, schedule bounds, safe heights, focal/CTA validation, carousel and popup API fields, duplication, ordering, thumbnail, and preview behavior.
- [x] Run them and confirm failures are caused by absent controls.
- [x] Add model fields/validation, migrations, serializer fields, and admin actions/read-only preview helpers.
- [x] Re-run CMS tests and existing storefront contracts.

### Task 3: Harden image uploads and generate safe derivatives

**Files:**
- Create: `backend/config/media.py`
- Modify: `backend/landing/models.py`, `backend/catalog/models.py`, `backend/catalog/admin.py`
- Create: `backend/catalog/migrations/0004_task5a_product_media.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- `validate_image_upload(file)` enforces configured bytes/dimensions/pixel/decompression limits and MIME agreement.
- `safe_image_upload_to(prefix)` removes the client filename and returns a UUID-based safe path.
- `generate_image_derivatives(*, storage, name, supported_formats=None) -> dict[str, str]` retains the original and produces AVIF/WebP where supported plus an optimized JPEG fallback.

- [x] Write uploaded-file tests for spoofed MIME, oversize bytes/dimensions, decompression protection, unsafe names, original retention, and converter fallback.
- [x] Run the media tests and capture RED.
- [x] Implement shared validators/path generation/derivatives and wire landing/product media fields.
- [x] Run media and serialization regressions with isolated temporary `MEDIA_ROOT`.

### Task 4: Catalog import/export and inventory history

**Files:**
- Create: `backend/catalog/admin_io.py`
- Create: `backend/templates/admin/catalog/product/import_csv.html`
- Modify: `backend/catalog/admin.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- `validate_product_csv(upload) -> list[ProductImportRow]` returns all row errors before writes.
- `import_products_csv(upload, *, dry_run, actor) -> ImportResult` is atomic and dry-run safe.
- `export_products_csv(queryset) -> bytes` includes admin-only cost/price/stock and neutralizes formula cells.

- [x] Write literal CSV tests for valid dry-run/no writes, multi-row validation/no partial writes, formula neutralization, export columns, variant/media/attribute inlines, and inventory history visibility.
- [x] Capture RED.
- [x] Implement import/export services and guarded admin URLs/actions.
- [x] Re-run catalog tests and confirm public catalog still excludes cost.

### Task 5: Guarded order actions and audited fiscal/order exports

**Files:**
- Create: `backend/commerce/admin_services.py`
- Create: `backend/commerce/exports.py`
- Modify: `backend/commerce/models.py`, `backend/commerce/admin.py`, `backend/accounts/models.py`, `backend/accounts/admin.py`
- Create: `backend/commerce/migrations/0013_task5a_admin_permissions_and_exports.py`
- Create: `backend/accounts/migrations/0004_task5a_sensitive_export_permission.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- `perform_order_admin_action(*, action, order, actor, reason, adapters=None)` checks the action permission then invokes the existing identity/checkout/payment/shipping service and writes a bounded audit event.
- CSV/XLSX exporters accept actor, queryset, filters and sensitive permission; every export writes `StaffExportAudit` with actor/time/format/filter/count and never the exported data.
- Spreadsheet cells beginning with `=`, `+`, `-`, or `@` are prefixed with an apostrophe.

- [x] Write permission-denial and audited-success tests for guarded actions without direct model state writes.
- [x] Write masked/unmasked permission tests for CSV and XLSX plus formula-injection and audit-log assertions.
- [x] Capture RED.
- [x] Implement the action dispatcher, custom permissions, immutable audit model, exporters, and admin actions/download views.
- [x] Run sensitive-operation and export regressions.

### Task 6: Verification and evidence

**Files:**
- Modify: `.superpowers/sdd/implementation-plan/task-5a-admin-report.md`

- [x] Run full SQLite, PostgreSQL-relevant tests, Ruff, Django check, migration drift, OpenAPI, and collectstatic.
- [x] Verify the staged diff contains only backend/admin assets/report paths and no generated test media.
- [x] Append exact RED/GREEN and verification evidence to this report.
- [x] Commit explicit paths and report the hash and residual concerns.

## Implementation evidence

### RED boundaries

- Initial contract file: `13 failed` (`tests/test_task5a_admin_contracts.py`), covering absent roles/security/branding, CMS controls, media hardening, catalog I/O, guarded order actions and spreadsheet exports.
- Guarded action/readiness extension: `2 failed`, covering the five missing order service actions and bounded `/readyz` dependency state.
- Exact admin action visibility: `1 failed`, because actions were not yet filtered by their custom permissions.
- Closure review: `3 failed`, covering Owner group administration, accessible drag ordering and typed attribute inlines.

Every RED was observed before the corresponding production implementation.

### GREEN and compatibility

- Task 5A contract file after closure: `18 passed`.
- Related backend compatibility selection: `70 passed in 29.97s`.
- PostgreSQL Docker selection with `USE_POSTGRES_TEST_DB=true`: `30 passed in 140.07s` (locking, inventory, checkout, migration and Task 5A contracts).
- Full SQLite after the concurrent production-Compose repair and closure regressions: `187 passed, 13 skipped in 66.22s`.
- The preceding full run was `185 passed, 13 skipped, 1 failed`; its only failure was `docker compose config` missing the then-new concurrent `REDIS_PASSWORD`. It was reported to the infra owner and repaired exclusively in that scope; no Task 5A compatibility failure remains.

### Static and schema checks

- `ruff check .`: passed.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `python manage.py spectacular --format openapi-json --validate`: passed; schema output was written outside the repository and removed.
- `collectstatic --clear` under a temporary `STATIC_ROOT`: 166 files copied and 792 post-processed.
- Backend Docker development image rebuilt from hashed locks, including `openpyxl==3.1.5`.

### Operational contracts added in backend scope

- `/healthz`: liveness-only `200 {"status":"ok"}`.
- `/readyz`: `200` only when `SELECT 1` and Redis `PING` succeed; otherwise `503`. The response exposes only `ready|not_ready` and per-dependency `ok|unavailable`, with no connection strings, exception details or PII.
- Admin roles are synchronized idempotently to exact sets. Owner may manage the predefined groups; Catalog, Orders/Logistics and Content remain least privilege.
- CMS ordering supports pointer drag and keyboard `Alt+ArrowUp/ArrowDown`, while retaining editable numeric ordering as a non-JavaScript fallback.
- Image validation checks bytes, decoded MIME, dimensions and decompression limits; UUID paths discard client filenames and derivative failure retains the original plus an optimized safe fallback.
- Order actions require action-specific custom permissions and route through domain/provider services. Export audit rows store metadata only, never exported payloads.

## Fix Round 1 — review remediation

Review source: `task-5a-admin-review.md` at commit `5214afd` (11 REQUIRED, 4 OPTIONAL).

### RED/GREEN by finding cluster

- **R1–R2 admin security:** RED `4 failed`; GREEN `5 passed`. Production uses Django's Redis cache backend under the dedicated `admin_login` alias. Login reservations use atomic `add`/`incr`; development/test has an explicit locmem fallback. Two independent real Redis clients were also exercised concurrently in Docker. Required 2FA now fails startup without `ADMIN_2FA_PROVIDER`; a configured provider executes challenge/callback, rotates the session, binds verification to the staff user and is cleared by logout.
- **R3 responsive admin:** Playwright RED reproduced the 360 px overlap and 768 px overflow. GREEN measured 360/768/1024/1440 px with no document overflow or header/content overlap and minimum 44 px session/theme controls. Final header/content tops were `254.97/254.97`, `114.58/114.58`, `114.58/114.58`, and `65.78/65.78` px respectively.
- **R4–R5 and O1 CMS workflow:** RED `2 failed`; GREEN cluster passed. Reorder is a CSRF-protected admin POST using stable record IDs, `select_for_update`, global normalization and idempotent before/after semantics across 205 records. Pointer and `Alt+Arrow` interactions call that endpoint and announce completion through `aria-live`. Preview is permission-protected, record-specific and renders disabled/future content with desktop/mobile image, focal coordinates and responsive safe heights.
- **R6–R7 media lifecycle:** RED `3 failed`; GREEN `4 passed`. Stored extensions derive from decoded MIME, not the client suffix. Manifests contain bounded responsive widths with AVIF/WebP when supported and optimized JPEG fallback. Replacement/removal regenerates manifests and deletes superseded source/derivatives; landing and product serializers expose documented same-origin responsive source arrays.
- **R8–R9 and O3 catalog:** RED `3 failed`; GREEN `4 passed`. Admin stock is readonly except for a guarded adjustment route. Admin/CSV stock uses the locked inventory service and creates append-only movements with delta, actor, source and reference. CSV enforces byte/row limits and converts encoding/parser/header/duplicate/incompatible-slug failures to bounded validation results without partial writes.
- **R10–R11 orders:** RED `8 failed`; GREEN `9 passed`. Cancellation locks the order, is idempotent, releases active reservations, rejects paid/pending payments and shipped/fulfilled returns with stable safe codes, and creates one cancellation audit. Concurrent PostgreSQL cancellation produces one state transition/audit. Order Admin disables add/change bypasses, embeds readonly shipment status/tracking/safe label, and preserves service-only actions.
- **O2 sensitive action UX:** RED `1 failed`; GREEN passed. A final real-provider regression was then captured RED (`ProviderNotConfigured` escaped the bulk tracking action as HTTP 500) and GREEN (`1 passed`). Service actions require the operator's bounded reason, preserve it in audit, contain both domain and provider failures per order, and report eligible/ineligible outcomes without leaking provider messages or diagnostics.
- **O4 evidence:** the focused file now contains exactly `37 passed`, plus two PostgreSQL/Redis integration regressions in `test_postgres_task5a_admin.py`.

### Final Fix Round 1 evidence

- Focused SQLite in the locked backend image: `37 passed in 21.64s`.
- Full SQLite-compatible Docker suite: `205 passed, 17 skipped in 99.02s`; the skipped tests require explicit PostgreSQL/Redis or production-only topology and were exercised in their corresponding selections.
- PostgreSQL/Redis relevant suite, including the two real concurrency regressions: `53 passed in 104.96s`.
- Ruff: `All checks passed`.
- Django check under PostgreSQL Docker: `0 issues`.
- Migration drift under PostgreSQL Docker: `No changes detected`.
- OpenAPI JSON validation: exit `0`; responsive source arrays are typed through `ResponsiveMediaSource`.
- Isolated collectstatic: `166 static files copied`, `478 post-processed`.
- Playwright keyboard reorder: row ID changed and live status was `Elemento movido a la posición visible 2; orden global guardado.`
- Playwright responsive assertions at 360/768/1024/1440 showed document widths exactly matching each viewport, header bottom equal to content top (`254.97`, `114.58`, `114.58`, `65.78` px), and minimum interactive header control height `44` px.
- Playwright screenshots were written only to `%TEMP%`; no generated media/schema/browser artifact is committed.
