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

## Fix Round 1 independent verdict

Review target: `b1ded28f6e52e2649d76150e0c192ea1bccef7df`

### Verdict

- **RESOLVED: 9** — R1, R2, R7, R8, R9, R10, R11, O1 and O3.
- **PARTIAL: 6** — R3, R4, R5, R6, O2 and O4.
- **UNRESOLVED: 0**.
- **SPEC COMPLIANCE: FAIL.** Three core CMS/media findings and the required mobile Admin presentation remain partial. The payment retry defect recorded under O2 is also a release-safety concern.
- **CODE QUALITY: NEEDS WORK.** The implementation is substantially stronger and all committed gates pass, but the suite still misses six reproduced boundary failures.

### Independent verification

The review ran from an isolated archive of the exact commit; concurrent Task 5B files in the shared worktree were neither loaded into the test artifact nor modified.

- Focused SQLite: `37 passed, 2 skipped in 13.08s` for `test_task5a_admin_contracts.py` plus `test_postgres_task5a_admin.py`. The two skips are the explicit external PostgreSQL/Redis cases.
- Full SQLite-compatible suite: `207 passed, 15 skipped in 75.01s`.
- Exact 53-test PostgreSQL/Redis selection: `53 passed in 221.78s`, using fresh isolated PostgreSQL 17 and Redis 7 containers. The dedicated cross-client Redis throttle and concurrent cancellation tests also passed alone: `2 passed in 32.56s`.
- `ruff check .`, `manage.py check`, migration drift and OpenAPI JSON validation: all passed.
- Exact production cache alias in two separate Python processes used `RedisCache` and reserved the same key as `1`, then `2`.
- Real browser 2FA path completed login → `/admin/2fa/` → provider callback → Admin 200. Logout removed the 32-character session cookie.
- Real browser dashboard metrics at 360/768/1024/1440 px had exact document widths, header bottom equal to content top, and a minimum header-control height of 44 px.
- With 205 CMS records, keyboard reorder on actual page 2 changed IDs `101,102,103` to `102,101,103`, returned HTTP 200 and announced `Elemento movido a la posición visible 2; orden global guardado.`
- Real order detail rendered shipment status/tracking, suppressed an unsafe `javascript:` label as `Sin etiqueta`, exposed no Order add link and rendered no mutation submit button.

### Finding-by-finding status

#### R1 — RESOLVED: production throttle state is shared and atomic

**Files:** `backend/config/settings.py:35-45,247-253`, `backend/config/admin_security.py:15-33,79-110`, `backend/tests/test_postgres_task5a_admin.py:13-38`.

Production now uses the dedicated Redis-backed `admin_login` cache and the throttle uses atomic `add`/`incr`. Two independent real application processes observed the same counter, and the committed real-Redis concurrency test passed. Development/test retains an explicit local fallback.

#### R2 — RESOLVED: 2FA has a working provider lifecycle

**Files:** `backend/config/admin_security.py:36-76,113-140`, `backend/config/settings.py:245-259`, `backend/config/urls.py:4-18`.

Missing provider configuration fails startup, the challenge and callback are routed, verification is bound to the pending staff ID, the session rotates, and logout clears verification. The complete redirect chain was reproduced in a real browser, not only through direct session mutation.

#### R3 — PARTIAL: collision is fixed, but the 360 px header is still not an intentional mobile stack

**Files:** `backend/landing/static/admin/css/mycdigitalizacion.css:11-15,29-49`, `backend/templates/admin/base_site.html:11-15`.

There is no longer overlap or horizontal overflow, and controls measure 44 px at all four required widths. At 360 px, however, the literal separators between user-tool elements become anonymous grid items: the screenshot shows a standalone `.` row followed by three standalone `/` rows. The header grows to `254.97px` before content starts. R3 remains partial because the acceptance required an intentional, coherent mobile organization, not only non-overlap.

#### R4 — PARTIAL: drag/keyboard ordering is global, but the promised numeric fallback still corrupts it

**Files:** `backend/landing/admin.py:22-86`, `backend/landing/static/admin/js/mycd-sortable.js:22-60`.

The stable-ID endpoint locks and normalizes the global 205-record sequence; real page-2 keyboard movement and `aria-live` feedback work. But `list_editable = ("order",)` remains active. On actual page 2, changing record 102 from order `100` to `0` and pressing Django's normal Save returned success and left two records with `order=0`. Non-JavaScript/numeric ordering therefore retains the original cross-page corruption path.

#### R5 — PARTIAL: preview is protected and record-specific, but mobile-only content has no rendered image

**Files:** `backend/landing/admin.py:35-48,88-96,112-116`, `backend/templates/admin/landing/scheduledcontent/preview.html:5-13`.

Unauthenticated preview returns 302, while a staff user can inspect disabled/future record state, focal values and safe heights. The template only emits `<img>` when `desktop_image` exists. A valid mobile-only draft rendered one `<source>` and zero `<img>` elements at 360 px, so the picture displays no image. The public preview workflow is not complete for the allowed mobile-only model state.

#### R6 — PARTIAL: MIME/API and happy-path replacement work, but widths are unbounded and storage failure is non-atomic

**Files:** `backend/config/media.py:95-156`, `backend/landing/models.py:103-136`, `backend/catalog/models.py:169-196`, `backend/landing/serializers.py:29-72`, `backend/catalog/serializers.py:23-44`.

Responsive manifests are now public, decoded MIME drives filenames, replacement/removal regenerate and clean assets on the happy path, and AVIF/WebP fallback behavior is covered. Two required lifecycle boundaries still fail:

1. With configured widths `(320, 640, 960, 1440)`, a 2000 px source produced `[320, 640, 960, 1440, 2000]`; the generator creates another full-width derivative even though the original is already retained separately.
2. A synthetic storage failure on the second write propagated while leaving `source-320.webp` beside the original. Model save happens before derivative publication, so there is no staging/rollback for partially written derivative sets.

#### R7 — RESOLVED: stored suffix follows decoded content

**Files:** `backend/config/media.py:12-39,46-90`, `backend/landing/models.py:48-57`.

Validation records the decoded extension and upload paths reject an undecoded format. The focused real-file tests cover spoofed MIME, wrong client suffix and public serialization, and pass.

#### R8 — RESOLVED: Admin and CSV stock changes are service-backed and audited

**Files:** `backend/catalog/admin.py:31-32,54-63,126-176`, `backend/catalog/admin_io.py:169-207`, `backend/commerce/inventory.py:8-35`, `backend/commerce/migrations/0014_inventorymovement_actor_inventorymovement_source.py`.

Direct Admin fields are readonly, the guarded adjustment route and committed CSV import call the locked inventory service, and movements retain delta, actor, source and reference atomically. The browser/API route and PostgreSQL gates passed.

#### R9 — RESOLVED: malformed/bounded CSV failures are recoverable

**Files:** `backend/catalog/admin_io.py:64-166`.

Byte and row limits, UTF-8 failure, parser/header errors, duplicate headers and incompatible existing slugs return bounded validation results. Dry-run and committed imports preserve the no-partial-write contract in the focused suite.

#### R10 — RESOLVED: cancellation has locked state, payment and return guards

**Files:** `backend/commerce/cancellation.py:8-58`, `backend/commerce/admin_services.py:23-41`, `backend/tests/test_postgres_task5a_admin.py:41-68`.

Shipped/fulfilled orders return the stable return-required error, paid and pending/attention payments are refused, active reservations are released, cancelled retries are idempotent and concurrent PostgreSQL calls create one transition/audit. Both focused and real concurrency selections pass.

#### R11 — RESOLVED: Order Admin is operationally complete and read-only

**Files:** `backend/commerce/admin.py:34-73,103-143,259-286`.

Direct creation/change is disabled, shipment/tracking/status and a scheme-checked label are visible inline, and actions remain service/permission backed. The real change page exposed no add or save path and rendered the logistics fields safely.

#### O1 — RESOLVED: reorder announces keyboard movement

**File:** `backend/landing/static/admin/js/mycd-sortable.js:29-37,54-60`.

The real page-2 keyboard interaction returned focus to the row and populated the live region with its new visible position and global-save status.

#### O2 — PARTIAL: operator UX is bounded, but payment retry keys are still nondeterministic

**Files:** `backend/commerce/admin.py:76-82,145-190`, `backend/commerce/admin_services.py:50-55`.

Reasons are required and preserved; provider/domain failures are contained per selection and reported without diagnostics. Refund actions do not provide an idempotency key, so the dispatcher falls back to `uuid.uuid4()` on every attempt. In an actual database flow where the provider call raised after receiving the request, two identical Admin retries sent two different keys (`b1cc…` then `c0c5…`) and both local transactions rolled back to zero refunds. A provider that completed the first request can therefore process the second again. This is a payment-safety blocker despite O2's original optional classification.

#### O3 — RESOLVED: incompatible existing product slugs are file errors

**File:** `backend/catalog/admin_io.py:99-127`.

The importer now compares existing name/category and rejects incompatible metadata before writes. The focused conflict and dry-run tests pass.

#### O4 — PARTIAL: evidence is much stronger, but it still misses every residual boundary

**Files:** `backend/tests/test_task5a_admin_contracts.py`, `backend/tests/test_postgres_task5a_admin.py`, `.superpowers/sdd/implementation-plan/task-5a-admin-report.md`.

The focused file now contains 37 passing cases and the two real PostgreSQL/Redis cases are genuine. Full, integration, static and schema gates all pass. Coverage still does not exercise the malformed 360 grid/text-node layout, numeric page-2 fallback, mobile-only preview, over-cap derivative width, partial storage failure, or lost-response refund retry. All six escaped while the reported closure suite remained green.

### Final Fix Round 1 assessment

Fix Round 1 closes the shared-cache/2FA security boundary, MIME naming, audited inventory/CSV import, cancellation state machine, logistics visibility and keyboard announcement. It does not yet satisfy Task 5A. Editors can still corrupt global CMS order through the advertised numeric fallback, an allowed draft state cannot be visually previewed, derivative publication is neither bounded nor atomic, and Admin refund retries can send a second external operation with a new key. These are observable contract gaps, not style-only concerns.
