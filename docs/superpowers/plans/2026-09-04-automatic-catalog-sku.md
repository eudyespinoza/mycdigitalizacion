# Automatic Catalog SKU Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate immutable sequential product and variant SKU automatically, then renumber the existing catalog from `600001` in historical order.

**Architecture:** A singleton database sequence reserves product numbers under a row lock, while each product stores its next variant suffix and reserves it under a product-row lock. Model save paths generate missing SKU so every normal creation flow shares the same rule; management APIs, CSV imports, and UI treat SKU as read-only. A deterministic Django data migration rewrites current values and initializes both counters.

**Tech Stack:** Django 5, Django REST Framework, PostgreSQL/SQLite-compatible ORM locking semantics, pytest, Next.js/React, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-04-automatic-catalog-sku-design.md`

## Global Constraints

- Product SKU format is exactly six digits matching `6NNNNN`.
- Existing catalog numbering starts at `600001`; `600000` remains reserved.
- Variant SKU format is `<product-sku>-NN`, starting at `01` and ending at `99`.
- Assigned numbers are never reused.
- Existing products are ordered by `(created_at, id)`; existing variants are ordered by `id` because they have no creation timestamp.
- Existing `OrderItem.sku_snapshot` values remain unchanged.
- SKU is read-only in management API, Django Admin, forms, and CSV imports.
- CSV imports accept an old `sku` column but ignore it; exports continue to include generated SKU.
- Do not modify or commit unrelated `marketing/` or `output/` files.

---

### Task 1: Domain allocation and deterministic data migration

**Files:**
- Create: `backend/catalog/sku.py`
- Create: `backend/catalog/migrations/0008_automatic_catalog_skus.py`
- Modify: `backend/catalog/models.py`
- Test: `backend/tests/test_catalog_sku.py`

**Interfaces:**
- Produces: `reserve_product_sku() -> str`, returning the next `600001`-style value.
- Produces: `reserve_variant_sku(*, product_id: int) -> str`, returning the next `<base>-01`-style value.
- Produces: `CatalogSkuSequence(key="product", next_value: int)` and `Product.sku`, `Product.next_variant_sequence`.
- Consumes: Django transactions and row locking; no management-layer input is trusted.

- [ ] **Step 1: Write failing allocation tests**

Add tests that create products without SKU and variants without SKU, then assert:

```python
first = Product.objects.create(category=category, name="Primero", slug="primero")
second = Product.objects.create(category=category, name="Segundo", slug="segundo")
assert (first.sku, second.sku) == ("600001", "600002")

one = ProductVariant.objects.create(product=first, **variant_values())
two = ProductVariant.objects.create(product=first, **variant_values(name="Dos"))
assert (one.sku, two.sku) == ("600001-01", "600001-02")
```

Also assert a deleted suffix is not reused, changing either SKU raises `ValidationError`, product exhaustion above `699999` fails, and variant suffix 100 fails without persisting the variant.

- [ ] **Step 2: Run the focused tests and confirm the missing behavior**

Run: `docker compose run --rm backend pytest tests/test_catalog_sku.py -q`

Expected: failures because product SKU, counters, and reservation functions do not exist.

- [ ] **Step 3: Implement the allocator and final model state**

Implement `backend/catalog/sku.py` with exact constants and signatures:

```python
PRODUCT_SKU_START = 600001
PRODUCT_SKU_END = 699999
VARIANT_SEQUENCE_END = 99

def reserve_product_sku() -> str: ...
def reserve_variant_sku(*, product_id: int) -> str: ...
```

Both functions use `transaction.atomic()` and `select_for_update()`. `reserve_product_sku` locks `CatalogSkuSequence(pk="product")`, validates the upper bound, increments `next_value`, and returns `f"{value:06d}"`. `reserve_variant_sku` locks the product, validates `next_variant_sequence <= 99`, increments it with an ORM update, and returns `f"{product.sku}-{value:02d}"`.

Add these fields/models:

```python
class CatalogSkuSequence(models.Model):
    key = models.CharField(max_length=32, primary_key=True)
    next_value = models.PositiveIntegerField()

class Product(models.Model):
    sku = models.CharField(max_length=6, unique=True, editable=False)
    next_variant_sequence = models.PositiveSmallIntegerField(default=1, editable=False)
```

Keep `ProductVariant.sku` wide enough for legacy test/fixture compatibility, set it `editable=False`, generate it only when blank, and reject mutation after persistence. Wrap reservation plus insert in one atomic block so a failed insert rolls back its reserved value.

- [ ] **Step 4: Add migration and migration-focused tests**

Create migration `0008_automatic_catalog_skus.py` that:

1. creates `CatalogSkuSequence`;
2. adds nullable `Product.sku` and `Product.next_variant_sequence`;
3. rewrites every variant to a unique temporary value such as `__sku_tmp_<id>`;
4. orders products by `created_at`, `id` and assigns bases from `600001`;
5. orders each product's variants by `id`, assigns suffixes from `01`, and stores the next suffix;
6. creates the singleton counter at the next unused product number;
7. makes `Product.sku` non-null and unique and marks both SKU fields non-editable in migration state.

Use `MigrationExecutor` in the test to seed the pre-0008 state with deliberately conflicting legacy strings, migrate forward, and assert deterministic new values plus unchanged `commerce.OrderItem.sku_snapshot`.

- [ ] **Step 5: Run domain and migration tests**

Run: `docker compose run --rm backend pytest tests/test_catalog_sku.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the domain slice**

```bash
git add backend/catalog/models.py backend/catalog/sku.py backend/catalog/migrations/0008_automatic_catalog_skus.py backend/tests/test_catalog_sku.py
git commit -m "feat: generate sequential catalog skus"
```

---

### Task 2: Read-only SKU management contracts and search

**Files:**
- Modify: `backend/backoffice/catalog_serializers.py`
- Modify: `backend/backoffice/catalog_views.py`
- Modify: `backend/catalog/admin.py`
- Test: `backend/tests/test_backoffice_catalog.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- Consumes: `Product.sku`, automatic blank-SKU allocation from Task 1.
- Produces: `ManagementProductSerializer.sku: str` and `ManagementProductSummarySerializer.sku: str` as read-only output.
- Produces: variant `sku` as read-only output; create/update payloads no longer require it.

- [ ] **Step 1: Write failing management-contract tests**

Add API tests asserting:

```python
response = client.post("/api/v1/management/products/", payload_without_sku, format="json")
assert response.status_code == 201
assert response.json()["sku"] == "600001"
assert response.json()["variants"][0]["sku"] == "600001-01"
```

Send fake product and variant SKU values in a second request and assert the server ignores them. Patch an existing record with changed SKU strings and assert stored values remain unchanged. Search once with the six-digit base and once with the full variant SKU and assert the product is returned.

- [ ] **Step 2: Run tests and verify the current serializer rejects missing SKU**

Run: `docker compose run --rm backend pytest tests/test_backoffice_catalog.py tests/test_task5a_admin_contracts.py -q`

Expected: the new tests fail because SKU is writable/required and products do not expose a base SKU.

- [ ] **Step 3: Make serializers, query, and Admin read-only**

Add `sku` to both product serializer field lists with `read_only=True`. Mark `ManagementVariantSerializer.sku` read-only, remove supplied-SKU duplicate validation, and let `_save_variant` create new variants without `sku`.

Extend product-list search to:

```python
Q(sku__icontains=search) | Q(variants__sku__icontains=search)
```

Expose product/variant SKU in Django Admin `readonly_fields` and useful list/search columns without allowing edits.

- [ ] **Step 4: Run the focused management tests**

Run: `docker compose run --rm backend pytest tests/test_backoffice_catalog.py tests/test_task5a_admin_contracts.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the management slice**

```bash
git add backend/backoffice/catalog_serializers.py backend/backoffice/catalog_views.py backend/catalog/admin.py backend/tests/test_backoffice_catalog.py backend/tests/test_task5a_admin_contracts.py
git commit -m "feat: expose catalog skus as read only"
```

---

### Task 3: Automatic SKU in CSV import and generated SKU in export

**Files:**
- Modify: `backend/catalog/admin_io.py`
- Test: `backend/tests/test_task5a_admin_contracts.py`

**Interfaces:**
- Consumes: model-level automatic SKU generation from Task 1.
- Produces: imports that do not require `sku`; optional legacy `sku` input is ignored.
- Produces: exports with the persisted generated variant SKU.

- [ ] **Step 1: Write failing CSV compatibility tests**

Create one valid import without a `sku` header and one with `sku=LEGACY-MANUAL`. Assert both create variants whose values match `^6\d{5}-\d{2}$` and neither stores `LEGACY-MANUAL`. Keep an export assertion that the row contains the generated value.

- [ ] **Step 2: Run the CSV contract test and see it fail**

Run: `docker compose run --rm backend pytest tests/test_task5a_admin_contracts.py -q -k "csv or import or export"`

Expected: the no-SKU import is rejected and the legacy value is currently persisted.

- [ ] **Step 3: Split import requirements from export columns**

Define required import columns without `sku`, accept extra legacy columns, remove SKU from `ProductImportRow`, and omit `sku=` when creating a variant. Keep export headers and rows including the database-generated SKU. Remove duplicate validation based on an incoming SKU while retaining product/slug/category and numeric validation.

- [ ] **Step 4: Run CSV tests**

Run: `docker compose run --rm backend pytest tests/test_task5a_admin_contracts.py -q -k "csv or import or export"`

Expected: all matching tests pass.

- [ ] **Step 5: Commit the CSV slice**

```bash
git add backend/catalog/admin_io.py backend/tests/test_task5a_admin_contracts.py
git commit -m "feat: assign skus during catalog import"
```

---

### Task 4: Management UI displays automatic SKU without edit controls

**Files:**
- Modify: `frontend/lib/management/catalog-types.ts`
- Modify: `frontend/components/management/product-editor.tsx`
- Modify: `frontend/components/management/product-table.tsx`
- Test: `frontend/components/management/product-editor.test.tsx`
- Test: `frontend/components/management/product-table.test.tsx`

**Interfaces:**
- Consumes: management API product `sku` and variant `sku` read-only strings from Task 2.
- Produces: `ManagementProduct.sku: string`; `ProductEditorPayload.variants` omits `sku`.
- Produces: visible read-only labels for existing SKU and “Se asignará al guardar” for unsaved records.

- [ ] **Step 1: Read the relevant installed Next.js guides**

Read:

```text
frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md
frontend/node_modules/next/dist/docs/01-app/02-guides/forms.md
```

Keep the existing client component boundary and controlled-form conventions.

- [ ] **Step 2: Write failing component tests**

Render an existing product and assert `600001` and `600001-01` are visible with no textbox named SKU and no “Generar SKU” button. Render a new product and assert “Se asignará al guardar” is shown. Submit and assert the request body contains no product or variant `sku` key. Render the product table and assert its SKU column uses `product.sku`, not `product.variants[0].sku`.

- [ ] **Step 3: Run component tests and verify failure**

Run: `npm run test:run -- components/management/product-editor.test.tsx components/management/product-table.test.tsx`

Working directory: `frontend`

Expected: tests fail because the editor still exposes a generated editable SKU and the table shows the first variant SKU.

- [ ] **Step 4: Remove manual SKU state and show read-only values**

Delete `skuTokens`, `generateSku`, `generateVariantSku`, the editable SKU input, and its generation button. Preserve response SKU on existing variant drafts for display only, omit it from submitted payloads, and add a compact read-only product SKU field. Update TypeScript contracts so payload variants no longer require `sku`. Change the table SKU cell to `product.sku`.

- [ ] **Step 5: Run frontend tests and type/build checks**

Run from `frontend`:

```bash
npm run test:run -- components/management/product-editor.test.tsx components/management/product-table.test.tsx
npm run build
```

Expected: component tests and production build pass.

- [ ] **Step 6: Commit the UI slice**

```bash
git add frontend/lib/management/catalog-types.ts frontend/components/management/product-editor.tsx frontend/components/management/product-table.tsx frontend/components/management/product-editor.test.tsx frontend/components/management/product-table.test.tsx
git commit -m "feat: show automatic sku in catalog management"
```

---

### Task 5: Regression verification and migration rehearsal

**Files:**
- Modify only if a focused regression reveals an SKU-contract defect in files already listed above.

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: evidence that schema, API, CSV, UI, and existing commerce behavior remain compatible.

- [ ] **Step 1: Check migration consistency**

Run: `docker compose run --rm backend python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

- [ ] **Step 2: Run the complete backend suite**

Run: `docker compose run --rm backend pytest -q`

Expected: all backend tests pass. Existing tests may continue to provide explicit legacy SKU through direct ORM fixture construction, but no user-facing creation path may accept one.

- [ ] **Step 3: Run the complete frontend suite and build**

Run from `frontend`:

```bash
npm run test:run
npm run build
```

Expected: all frontend tests and the production build pass.

- [ ] **Step 4: Rehearse migrations on the Compose database**

Run:

```bash
docker compose run --rm backend python manage.py migrate
docker compose exec db psql -U postgres -d mycdigitalizacion -c "select sku, name from catalog_product order by created_at, id limit 10;"
docker compose exec db psql -U postgres -d mycdigitalizacion -c "select p.sku, v.sku from catalog_product p join catalog_productvariant v on v.product_id=p.id order by p.created_at, p.id, v.id limit 20;"
```

Expected: product values start at `600001`, variants share their product base and increase from `01`, and there are no duplicate values.

- [ ] **Step 5: Review the final diff and commit any focused fixes**

Run: `git -c safe.directory=D:/mycdigitalizaciones diff --check`

Stage only SKU-related files. Do not add `marketing/` or `output/`.
