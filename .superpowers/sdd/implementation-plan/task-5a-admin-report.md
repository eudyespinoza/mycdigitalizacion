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

## Fix Round 2 — residual boundary closure

Review source: appended **Fix Round 1 independent verdict** in `task-5a-admin-review.md` for commit `b1ded28`.

### RED/GREEN evidence

- **R3 compact mobile Admin:** rendered Admin RED exposed no semantic session/link groups and retained punctuation text nodes that became anonymous grid rows. GREEN overrides the user-tools block with semantic groups and no standalone `.` or `/`. Real Playwright at 360 px reduced header height from `254.97` to `165.97` px, found zero orphan direct text nodes, exact document width, no content overlap, and minimum control height `44` px. The 768/1024/1440 px metrics remain `114.58`, `114.58`, and `65.78` px with no overflow or overlap.
- **R4 global ordering bypass:** real page-2 Admin POST RED changed the record at global order `100` to `0`, leaving two records at order zero. GREEN removes `list_editable`; the locked stable-ID reorder endpoint is now the only mutation path. A real page-2 browser had zero numeric order inputs and keyboard reorder still moved ID `1` after ID `2` with the `aria-live` confirmation.
- **R5 preview media fallback:** the three-shape table test reproduced mobile-only as RED: a mobile `<source>` existed but there was no visible `<img>`. GREEN uses desktop as the default `<img>` when present and mobile otherwise, preserving the mobile `<source>`, focal coordinates and all three safe heights for desktop-only, mobile-only and both-image records.
- **R6 bounded/atomic derivatives:** four RED outcomes were captured: a 2000 px source emitted an unwanted 2000 px derivative above configured cap; second-write failure left `source-320.webp`; and landing/catalog replacement failures persisted the new DB source and leaked the uploaded source. GREEN caps output at the largest configured responsive width while retaining the original separately, cleans all partial derivative writes on any publication exception, wraps DB publication in a savepoint, removes new assets on rollback, and preserves prior source/manifests for both models.
- **O2 deterministic refund recovery:** local-loss RED sent two different provider idempotency keys and left zero local refunds after the first rollback. PostgreSQL concurrency RED correctly reused the provider operation after the initial key repair but wrote two completion audits. GREEN derives a stable UUIDv5 from the order public ID, reconciles the repeated approved response into one local Refund, and serializes concurrent retries to one provider operation, one Refund and one completion audit.
- **O4 negative coverage:** `test_task5a_fix_round2.py` contains the exact R3/R4/R5/R6/O2 negative boundaries, and `test_postgres_task5a_admin.py` contains the real concurrent refund regression.

### Final Fix Round 2 verification

- Focused Task 5A contracts: `47 passed in 32.06s`.
- Full shared SQLite-compatible suite: `219 passed, 18 skipped in 122.67s`.
- PostgreSQL/Redis relevant suite: `64 passed in 134.87s`.
- Ruff: `All checks passed`.
- Django check under PostgreSQL Docker: `0 issues`.
- Migration drift under PostgreSQL Docker: `No changes detected`; no migration is required for this round.
- OpenAPI JSON validation: exit `0`; the existing responsive-source schema is unchanged.
- Isolated collectstatic: `166 static files copied`, `478 post-processed`.
- Browser and schema outputs used temporary storage only; the temporary Playwright PostgreSQL database and server were removed after verification.

## Fix Round 3 — final independent-review closure

Review source: final appended verdict in `task-5a-admin-review.md` for the Fix Round 2 boundary.

### Exact RED/GREEN regressions

- **R3 mobile header hit target:** real Playwright at 360 px reproduced RED with the theme button at `x=-12`, width `360`, and `elementFromPoint` over the logo returning `BUTTON.theme-toggle`. The mobile full-width rule now excludes the theme button and gives it an explicit 44 px width. GREEN measured the theme control at `x=304`, `44x44`, with the brand hit returning its correct link target `A` and no theme overlay. The same assertions at 360/768/1024/1440 px found exact document widths, no brand/control overlap, minimum 44 px controls, and header/content boundaries of `165.97`, `114.58`, `114.58`, and `65.78` px.
- **R4 direct order bypasses:** a real Admin change-form POST reproduced RED by accepting `order=0` for the record initially at order 101, creating a duplicate zero. `order` is now readonly on every scheduled-content change form, so the locked stable-ID reorder service is the only write path. GREEN proves the same POST leaves order 101 and exactly one zero. A separate regression GETs the real `?p=2` ChangeList, selects a record from that rendered result page, submits the former formset payload, and proves its order remains unchanged and globally unique at zero.
- **R6 intermediate source width:** a 1000 px source with configured widths 320/640/960/1440 reproduced RED as `[320, 640, 960, 1000]`, duplicating the original width. GREEN is exactly `[320, 640, 960]`: every generated width is configured and strictly smaller than the source, while the original remains stored and each width retains its optimized fallback. Existing small/replacement tests now assert this same contract instead of expecting an original-width derivative.
- **O4 exact evidence:** committed negatives cover the actual change URL, an actual `?p=2` result page, and the intermediate-width media case. The 360 px CSS hit-test was executed before and after the selector repair against the real rendered Admin, including `elementFromPoint`, bounding boxes and four viewport sizes.

### Final Fix Round 3 verification

- Focused Task 5A contracts: `49 passed in 41.68s`.
- Full SQLite-compatible suite at the exact reviewed commit: `224 passed, 16 skipped`.
- PostgreSQL/Redis relevant suite: `66 passed in 161.00s`.
- Ruff after the final test cleanup: `All checks passed`.
- Django check with `DJANGO_DEBUG=false`: `0 issues`.
- Migration drift: `No changes detected`; this round requires no migration.
- OpenAPI JSON generation and validation: exit `0`.
- Isolated collectstatic: `166 static files copied`, `792 post-processed`.
- No browser screenshot, schema, temporary database or generated media artifact is included in this change. Concurrent Task 5B infra edits visible in the shared worktree were excluded from the explicit Task 5A commit.
