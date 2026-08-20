# Task 5A — independent admin/CMS/media backend review

Review target: `83c8d96c552f2c28b335504a91c86cdee3528787`

Specification: `.superpowers/sdd/implementation-plan/task-5-brief.md`, lines 5–17 and 24–28

Scope: Django Admin, CMS, catalog/order operations, exports and media backend only. Concurrent production/Compose/ops work was excluded and left untouched.

## Verdict

- **SPEC COMPLIANCE: FAIL — 11 REQUIRED findings.** The commit establishes a useful base, but admin authentication, mobile layout, CMS ordering/preview, responsive media, inventory auditability and guarded order operations do not yet meet the Task 5 contract.
- **CODE QUALITY: NEEDS WORK — 4 OPTIONAL findings.** The code is generally small and readable and the existing regression suite is green, but important negative/stateful paths are not tested and several admin interactions need production-grade failure handling and accessibility polish.
- **Counts:** 11 REQUIRED, 4 OPTIONAL.

## Verification evidence

- Review ran from an isolated archive of the exact commit so concurrent workspace changes could not affect results.
- `python -m pytest -q tests/test_task5a_admin_contracts.py`: **17 passed** in 8.50 s.
- `python -m pytest -q`: **187 passed, 13 skipped** in 62.98 s.
- Eight isolated negative reproductions passed while asserting the current defective outcomes: stale/full-size derivatives, suffix/content mismatch, terminal-order cancellation, unaudited stock edit, missing 2FA endpoint, absent shipment fields, exposed direct Order add path, and uncaught invalid CSV encoding.
- Real Playwright/Django live-server render: 360×800 and 1440×900 captured from the exact commit. The dashboard had no document-level horizontal overflow, but the 360 px header visibly overlapped; the 1440 px render remained structurally usable.
- `python -m ruff check .` against the exact product/test sources (excluding the temporary review-only reproduction files): **passed**.
- `python manage.py check`: **0 issues**.
- `python manage.py makemigrations --check --dry-run`: **No changes detected**. The command warned that the locally configured PostgreSQL credentials were unavailable, so this is a state-drift check, not an independent PostgreSQL integration run.
- Public catalog confirmation: `catalog/serializers.py:72-93` exposes price and stock but no `cost`; the commit test also confirms `/api/v1/products/{slug}/` omits cost.
- Export confirmation: `commerce/exports.py:9-30,44-96` neutralizes spreadsheet formulas, masks by the sensitive-data permission, writes CSV/XLSX, and records metadata-only audit rows. No ARCA issuance was added.

## REQUIRED findings

### R1. Admin brute-force state is process-local, so production workers do not share a lock window

**Files:** `backend/config/admin_security.py:18-40`, `backend/config/settings.py:227-230`.

`RateLimitedAdminAuthenticationForm` reads and writes Django's default cache, but the commit never configures `CACHES`. At runtime, `settings.CACHES` resolves to `django.core.cache.backends.locmem.LocMemCache`. Each Gunicorn process therefore maintains a different counter; attempts routed across workers can evade the intended maximum, and restarts erase the lock.

**Reproduction:** load the exact settings and print `settings.CACHES`; it returns `{'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}`. The focused test exercises one process only.

**Required:** configure a shared atomic cache (the existing Redis service is the natural target), use atomic increment/add behavior, and test attempts split across independent cache clients/workers. Local development may retain an explicit local fallback.

### R2. Enabling the advertised 2FA configuration sends staff to an unimplemented endpoint

**Files:** `backend/config/admin_security.py:44-68`, `backend/config/settings.py:229-230`, `backend/config/urls.py:10-14`, `backend/tests/test_task5a_admin_contracts.py:112-126`.

The middleware redirects to `/admin/2fa/` and trusts a manually injected `admin_2fa_verified` session value, but there is no verification view, URL, provider callback or code that sets that value. The test stops after asserting the redirect and mutates the session itself, so it does not prove an operational 2FA-ready path.

**Reproduction:** with `ADMIN_2FA_REQUIRED=True`, an authenticated staff GET to `/admin/2fa/` returns **404**. The default setting therefore locks staff out instead of starting verification.

**Required:** provide a real pluggable verification route/callback and session lifecycle, or fail startup when 2FA is required without a configured provider/URL. Test login → challenge → verified admin access and logout/session rotation.

### R3. The branded admin header overlaps at the required small viewport

**Files:** `backend/templates/admin/base_site.html:11-15`, `backend/landing/static/admin/css/mycdigitalizacion.css:11-18,23-28`.

At 360×800, the user-tools links wrap to several lines and extend through the bottom of the dark header; `Operaciones` begins underneath that text. This is a real visual/readability collision even though the document does not horizontally overflow. The mobile rule changes alignment but does not reserve height or reorganize `#user-tools`.

**Reproduction:** run the exact commit under a Django live server, sign in as staff, and capture `/admin/` with a 360×800 viewport. The collision is visible around the header/title boundary. At 1440×900 it does not occur.

**Required:** define an intentional mobile header stack/wrap for brand, session controls and theme toggle, with no overlap at 360, 768, 1024 and 1440 px; preserve visible keyboard focus and 44 px touch targets.

### R4. CMS drag/keyboard ordering corrupts global order on paginated changelists

**Files:** `backend/landing/admin.py:14-24`, `backend/landing/static/admin/js/mycd-sortable.js:8-23,25-64`.

`synchronize()` assigns each visible row `0..N-1`. Django changelists paginate, so moving any item on page 2 rewrites those rows to the same order values as page 1. The resulting duplicates break the promised global drag/reorder semantics. The focused test only checks that the asset is present and never exercises multiple pages.

**Reproduction:** create more than one changelist page of hero slides, open page 2, use Alt+Arrow to move a row and save; page-2 `order` inputs restart at zero and collide with page 1.

**Required:** use a server-authoritative ordering operation with stable IDs and page offsets (or an explicitly unpaginated bounded ordering UI), preserve concurrency/idempotency, and cover first/middle/last page plus keyboard ordering.

### R5. “Vista pública” cannot preview the content being edited

**Files:** `backend/landing/admin.py:40-42`, `backend/api_views.py` `StorefrontHomeView.get` scheduled filtering, `backend/landing/models.py:90-96`.

Every CMS row links to the same public `/` page. Disabled, future or expired content is intentionally omitted by the public API, so the editor cannot preview those records; even enabled records are not targeted/highlighted. This does not satisfy thumbnail/**preview** workflow for unpublished content.

**Reproduction:** create a disabled hero slide, click “Abrir portada”; the home API excludes the slide and the link contains no record/token context.

**Required:** provide a permission-protected, record-specific preview that renders draft/scheduled presentation data without publishing it, and test disabled/future content and desktop/mobile image/focal/height controls.

### R6. Image derivatives are neither responsive nor lifecycle-correct, and clients cannot consume them

**Files:** `backend/config/media.py:84-116`, `backend/landing/models.py:104-118`, `backend/catalog/models.py:166-175`, `backend/landing/serializers.py:26-56`, `backend/catalog/serializers.py:22-31`.

The generator re-encodes exactly one AVIF/WebP/fallback at the original dimensions; it never creates width variants. Model saves generate only when the derivative JSON is empty, so replacing an image retains derivative paths/content for the previous image. Finally, public serializers expose only the original URL, not any derivative manifest/srcset. The feature is therefore storage work with no responsive delivery path.

**Reproduction:** save a 320×180 hero, then replace it with 160×90. `desktop_derivatives` remains byte-for-byte unchanged and the referenced WebP is still 320×180. Serializer field lists contain no derivatives. The same guard exists for `ProductMedia`.

**Required:** generate bounded responsive widths per desktop/mobile source, regenerate atomically whenever the source changes, clean up superseded assets safely, retain the original, expose a stable public derivative contract, and test converter fallback plus replacement/removal.

### R7. Stored filename suffix can contradict decoded MIME (or become unusable `.bin`)

**Files:** `backend/config/media.py:20-32,39-81`, `backend/catalog/models.py:150-175`.

Validation compares supplied `content_type` with decoded content but never compares the client filename suffix with decoded format. `SafeImageUploadTo` independently trusts the client suffix; unsupported suffixes become `.bin`. Consequently a valid PNG uploaded as `wrong.jpg` with `image/png` is accepted and stored as `.jpg`, while a valid product image named without an allowed suffix becomes `.bin`. Static/media servers commonly derive response MIME from that suffix, so a validated image can be served with the wrong type or fail to render.

**Reproduction:** upload PNG bytes as `wrong.jpg` with `content_type=image/png`; the model saves successfully, the stored path ends in `.jpg`, and Pillow identifies the stored bytes as PNG.

**Required:** derive the stored extension from decoded content (or reject extension/content mismatch) and cover missing/uppercase/unsupported filenames for both landing and product media.

### R8. Admin and CSV stock changes bypass inventory history

**Files:** `backend/catalog/admin.py:18-32,110-130`, `backend/catalog/admin_io.py:139-167`, `backend/catalog/models.py:225`, `backend/commerce/models.py` `InventoryMovement`.

Both the variant inline/admin and CSV importer write `ProductVariant.on_hand` directly. No `InventoryMovement` is created and the importer discards its `actor`. The “Historial” link therefore presents incomplete history precisely for the staff workflows added by this task.

**Reproduction:** update `on_hand` from the admin-equivalent model save; `InventoryMovement.objects.filter(variant=variant).count()` remains zero. A committed CSV row likewise creates a variant with stock but no movement/audit actor.

**Required:** route stock initialization/adjustment through an inventory service that locks the variant, records delta, actor/source/reference and remains atomic with import; make direct `on_hand` editing read-only or service-backed.

### R9. Invalid CSV encoding escapes as a server error instead of a row/file validation result

**Files:** `backend/catalog/admin_io.py:65-76`, `backend/catalog/admin.py:73-89`.

`raw.decode("utf-8-sig")` is unguarded, and the admin view calls the importer without handling decode/CSV/parser errors or bounding upload size. A malformed file therefore raises `UnicodeDecodeError` rather than returning the promised validation/dry-run result.

**Reproduction:** call `validate_product_csv(SimpleUploadedFile("broken.csv", b"\xff\xfe\x00\x00"))`; `UnicodeDecodeError` escapes. The admin POST consequently becomes a 500.

**Required:** bound upload bytes/row count, convert encoding/parser failures into actionable file-level errors, and keep the no-partial-write guarantee. Add malformed encoding, oversized input, duplicate headers and existing-slug conflict tests.

### R10. Guarded cancellation accepts impossible terminal transitions

**Files:** `backend/commerce/admin_services.py:23-41`, `backend/commerce/services.py:431-452`.

The cancel action delegates to a generic choice validator, not a transition policy. Any recognized fulfillment value is accepted from any current state. A fulfilled or shipped order can therefore become cancelled; this path also does not coordinate payment/refund/return or active reservations. Writing an audit event does not make the state change valid.

**Reproduction:** transition an order to `fulfilled`, grant `commerce.cancel_order`, then call `perform_order_admin_action(action="cancel", ...)`; it succeeds and returns `fulfillment_status="cancelled"`.

**Required:** implement a domain cancellation service with an explicit transition matrix, locked/idempotent state handling, reservation/payment/return semantics, and user-safe errors. Test unfulfilled, preparing, shipped, fulfilled, already-cancelled and retry/concurrency cases.

### R11. Order admin omits shipment/label/tracking and still exposes direct Order creation

**Files:** `backend/commerce/admin.py:65-104,212-235,272-285`.

`OrderAdmin` includes item and audit inlines only. Shipment is registered as a separate append-only model, with no inline/link/fields on the order detail; `tracking_number`, `label_url` and shipment status are absent. Conversely, `has_add_permission` is not overridden, so users with `add_order` (including Owner) see and can enter a direct model add path instead of checkout/domain services. The 360 and 1440 live renders both display “Agregar” for Orders.

**Reproduction:** inspect `OrderAdmin.inlines`/`readonly_fields`: Shipment and its required fields are absent. `OrderAdmin.has_add_permission()` returns true for a user with `commerce.add_order`.

**Required:** make order creation unavailable in Admin, show/link immutable shipment/label/tracking state on the order detail, and keep all sensitive actions service-only with state-aware availability and safe failure messages.

## OPTIONAL findings

### O1. Reordering is keyboard-operable but does not announce the result

**Files:** `backend/landing/static/admin/js/mycd-sortable.js:30-63`.

Rows receive a static instruction label and focus returns after movement, but there is no live region or updated positional label. Screen-reader users are not told that an item moved or its new position. Add an `aria-live` status and announce item/position; keep the numeric non-JS fallback.

### O2. Sensitive bulk actions use generic reasons and abort without per-order feedback

**Files:** `backend/commerce/admin.py:106-184`, `backend/commerce/admin_services.py:30-32,75-81`.

Every audit event records a hard-coded phrase rather than the operator's reason, and one provider/domain error interrupts the selection without an admin confirmation/result summary. Prefer a confirmation form with required reason, eligible/ineligible counts, per-order messages and deterministic retry keys.

### O3. Existing product slug conflicts are silently accepted by CSV import

**Files:** `backend/catalog/admin_io.py:80-136,145-166`.

When `product_slug` already exists, the importer attaches the new variant but ignores conflicting `product_name` and `category_slug`. Treat incompatible existing-product metadata as a row error (or make the update policy explicit) so a valid-looking dry run cannot file stock under the wrong product/category.

### O4. Tests and implementation evidence overstate closure

**Files:** `backend/tests/test_task5a_admin_contracts.py`, `.superpowers/sdd/implementation-plan/task-5a-admin-report.md` “Implementation evidence”.

The exact commit contains **17**, not the reported 18, Task 5A contract tests. Assertions mostly prove members/assets exist; they do not exercise shared-cache behavior, a real 2FA flow, paginated ordering, responsive browser widths, image replacement/srcsets, invalid CSV bytes, inventory movement, terminal cancellation or complete order detail. Add behavior-level negative tests and correct the evidence count.

## Remediation acceptance matrix (Current / Required / Why)

| Area | Current | Required acceptance state | Why |
|---|---|---|---|
| Admin auth | Per-process counters; dead default 2FA URL | Shared atomic throttling; end-to-end provider-backed challenge | Security controls must work under real multi-worker deployment |
| Admin UI | 360 px header collision; desktop usable | Collision-free 360/768/1024/1440 with preserved focus/touch targets | Coherent responsive staff experience |
| CMS | Local page indices and public-home “preview” | Global server-authoritative ordering and protected draft preview | Editors must control and inspect the exact content safely |
| Media | One full-size stale derivative, no public contract | Responsive width set, lifecycle regeneration and serialized source set | Optimized assets must actually reach storefront clients |
| Catalog | Direct stock writes; malformed CSV can 500 | Audited inventory service and bounded recoverable import errors | Inventory history and dry run must be trustworthy |
| Orders | Terminal cancel accepted; shipment absent; direct add exposed | Explicit state machine, service-only creation/actions, complete operational detail | Prevent impossible order states and support logistics work |
| Exports/cost | Masking, formula safety, audit and public cost exclusion work | Preserve current behavior with regression coverage | These parts meet the brief and must not regress |

## Final assessment

The commit is a credible foundation: exact role synchronization is idempotent, CMS scheduling/alt/focal/height/popup controls are represented in models/API, export masking/formula/audit behavior works, upload byte/dimension/decompression checks work, and cost remains private. It is not ready to accept as Task 5A because the production security and state-management boundaries fail outside the happy-path tests, and media/CMS/admin behavior is incomplete in real responsive use.
