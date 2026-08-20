# PgBouncer and Catalog Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce management-screen latency and accelerate catalog search, filters, facets, and pagination on the initial 2 GB Donweb VPS.

**Architecture:** Django, Celery Worker, and Celery Beat connect to PostgreSQL through a pinned PgBouncer 1.25.2 transaction pool on port 6432; migrations, backup, restore, and other operational commands retain a direct PostgreSQL connection. PostgreSQL performs candidate filtering, indexed search, and pagination before Django prefetches and serializes rows, while Redis stores short-lived catalog facets and configuration data under versioned keys.

**Tech Stack:** Docker Compose, PgBouncer 1.25.2, PostgreSQL 17, Django 5.2, Django REST Framework, Redis 7, Celery, pytest, unittest.

**Spec:** `docs/superpowers/specs/2026-08-20-pgbouncer-catalog-performance-design.md`

## Global Constraints

- Initial host budget is 2 GB RAM.
- PgBouncer uses `pool_mode=transaction`, `listen_port=6432`, `default_pool_size=10`, `min_pool_size=2`, `reserve_pool_size=2`, `max_client_conn=100`, `max_db_connections=20`, `server_idle_timeout=60`, `query_wait_timeout=15`, `server_reset_query=DISCARD ALL`, and SCRAM authentication.
- Django uses `CONN_MAX_AGE=0` and `DISABLE_SERVER_SIDE_CURSORS=True` on the pooled connection.
- `POSTGRES_DIRECT_HOST=postgres` and `POSTGRES_DIRECT_PORT=5432` are mandatory for migrations, backup, restore, and operational probes.
- No new search service is introduced; PostgreSQL full-text search and `pg_trgm` remain authoritative.
- Public stock, cart, checkout, identity, and payment state are never cached.
- Catalog facets expire after 60 seconds; categories and general branding expire after 300 seconds.
- Gunicorn starts with two workers and Celery starts with concurrency one.
- All new database changes must migrate from zero and upgrade the existing PostgreSQL database.

---

### Task 1: PgBouncer Topology and Direct Operational Connection

**Files:**
- Modify: `compose.yaml`
- Modify: `compose.prod.yaml`
- Modify: `.env.production.example`
- Modify: `backend/config/settings.py`
- Modify: `infra/ops/backup.py`
- Modify: `infra/ops/restore.py`
- Modify: `infra/ops/validate_env.py`
- Create: `infra/tests/test_pgbouncer_topology.py`
- Modify: `backend/tests/test_settings.py`

**Interfaces:**
- Consumes: existing `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` deployment variables.
- Produces: pooled application variables `POSTGRES_HOST=pgbouncer`, `POSTGRES_PORT=6432`; direct operational variables `POSTGRES_DIRECT_HOST=postgres`, `POSTGRES_DIRECT_PORT=5432`; Django helper `database_config(environment: Mapping[str, str]) -> dict[str, object]`.

- [ ] **Step 1: Write failing topology and settings tests**

```python
def test_production_apps_use_pgbouncer_and_operations_use_postgres_directly(rendered_compose):
    services = rendered_compose["services"]
    assert services["pgbouncer"]["environment"]["POOL_MODE"] == "transaction"
    assert services["backend"]["environment"]["POSTGRES_HOST"] == "pgbouncer"
    assert services["worker"]["environment"]["POSTGRES_PORT"] == "6432"
    assert services["backup"]["environment"]["POSTGRES_HOST"] == "postgres"
    assert services["assets-init"]["environment"]["POSTGRES_HOST"] == "postgres"

def test_pooled_database_settings_disable_session_state(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "pgbouncer")
    monkeypatch.setenv("POSTGRES_PORT", "6432")
    settings = database_config(os.environ)
    assert settings["CONN_MAX_AGE"] == 0
    assert settings["DISABLE_SERVER_SIDE_CURSORS"] is True
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `python -m unittest infra.tests.test_pgbouncer_topology -v`

Run: `docker compose run --rm backend pytest -q tests/test_settings.py -k pooled`

Expected: failures because PgBouncer, direct-host variables, and pooled Django options do not exist.

- [ ] **Step 3: Add PgBouncer and route application traffic through it**

Use `edoburu/pgbouncer:v1.25.2-p0`, a pinned release. Configure the service with:

```yaml
pgbouncer:
  image: edoburu/pgbouncer:v1.25.2-p0
  environment:
    DB_HOST: postgres
    DB_PORT: "5432"
    DB_NAME: ${POSTGRES_DB:-mycdigitalizacion}
    DB_USER: ${POSTGRES_USER:-mycdigitalizacion}
    DB_PASSWORD: ${POSTGRES_PASSWORD:-change-me-for-local-development}
    LISTEN_PORT: "6432"
    AUTH_TYPE: scram-sha-256
    POOL_MODE: transaction
    DEFAULT_POOL_SIZE: "10"
    MIN_POOL_SIZE: "2"
    RESERVE_POOL_SIZE: "2"
    MAX_CLIENT_CONN: "100"
    MAX_DB_CONNECTIONS: "20"
    SERVER_IDLE_TIMEOUT: "60"
    QUERY_WAIT_TIMEOUT: "15"
    SERVER_RESET_QUERY: DISCARD ALL
  healthcheck:
    test: [CMD-SHELL, 'pg_isready -h 127.0.0.1 -p 6432 -U "$$DB_USER" -d "$$DB_NAME"']
```

Set application services to `POSTGRES_HOST=pgbouncer` and `POSTGRES_PORT=6432`, require the PgBouncer health check, and keep `assets-init`, `backup`, and restore instructions on `POSTGRES_DIRECT_HOST`/`POSTGRES_DIRECT_PORT`.

- [ ] **Step 4: Add pooled Django settings and direct operational resolution**

Implement:

```python
def database_config(environment):
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": environment.get("POSTGRES_DB", "mycdigitalizacion"),
        "USER": environment.get("POSTGRES_USER", "mycdigitalizacion"),
        "PASSWORD": environment.get("POSTGRES_PASSWORD", "change-me-for-local-development"),
        "HOST": environment.get("POSTGRES_HOST", "localhost"),
        "PORT": environment.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
```

In `backup.py` and `restore.py`, resolve `POSTGRES_DIRECT_HOST` before `POSTGRES_HOST` and `POSTGRES_DIRECT_PORT` before `POSTGRES_PORT` for every PostgreSQL CLI call.

- [ ] **Step 5: Validate the focused topology**

Run: `python -m unittest infra.tests.test_pgbouncer_topology -v`

Run: `docker compose config --quiet`

Run: `docker compose --env-file .env.production.example -f compose.prod.yaml config --quiet`

Expected: all commands exit 0; applications depend on healthy PgBouncer and operational services resolve PostgreSQL directly.

- [ ] **Step 6: Commit Task 1**

```bash
git add compose.yaml compose.prod.yaml .env.production.example backend/config/settings.py backend/tests/test_settings.py infra/ops/backup.py infra/ops/restore.py infra/ops/validate_env.py infra/tests/test_pgbouncer_topology.py
git commit -m "feat: route application database traffic through pgbouncer"
```

### Task 2: PostgreSQL Indexes for Catalog and Management Lists

**Files:**
- Modify: `backend/catalog/models.py`
- Modify: `backend/commerce/models.py`
- Modify: `backend/accounts/models.py`
- Modify: `backend/backoffice/models.py`
- Modify: `backend/landing/models.py`
- Create: `backend/catalog/migrations/0006_catalog_performance_indexes.py`
- Create: `backend/commerce/migrations/0015_management_performance_indexes.py`
- Create: `backend/accounts/migrations/0005_customer_search_indexes.py`
- Create: `backend/backoffice/migrations/0002_audit_performance_indexes.py`
- Create: `backend/landing/migrations/0008_content_performance_indexes.py`
- Create: `backend/tests/test_postgres_performance_indexes.py`

**Interfaces:**
- Consumes: existing PostgreSQL `pg_trgm` extension from `catalog.0003_product_created_at`.
- Produces: stable named indexes `catalog_product_live_category_idx`, `catalog_product_live_brand_idx`, `catalog_product_search_gin`, `catalog_product_name_trgm`, `catalog_variant_sku_trgm`, plus management, reservation, promotion, customer, audit, and content indexes asserted by name.

- [ ] **Step 1: Write failing PostgreSQL index-contract tests**

```python
@pytest.mark.postgresql
def test_catalog_and_management_indexes_exist(django_db_blocker):
    required = {
        "catalog_product_live_category_idx",
        "catalog_product_live_brand_idx",
        "catalog_product_search_gin",
        "catalog_product_name_trgm",
        "catalog_variant_sku_trgm",
        "commerce_reservation_active_idx",
        "commerce_order_management_idx",
        "accounts_user_email_trgm",
        "backoffice_audit_resource_idx",
        "landing_content_schedule_idx",
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        assert required <= {row[0] for row in cursor.fetchall()}
```

- [ ] **Step 2: Run the PostgreSQL test and confirm RED**

Run: `docker compose run --rm -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql tests/test_postgres_performance_indexes.py`

Expected: failure listing the missing named indexes.

- [ ] **Step 3: Add model index state and non-atomic PostgreSQL migrations**

Use partial B-tree indexes for live product category/brand ordering, GIN indexes for Spanish search vectors and trigram name/SKU search, and composite B-tree indexes matching the exact management predicates. Each PostgreSQL migration must set `atomic = False` and use concurrent index creation. The product search expression is:

```sql
to_tsvector('spanish', coalesce(name, '') || ' ' || coalesce(description, ''))
```

The live product predicate is:

```sql
WHERE is_active AND is_sellable
```

The reservation index begins with `(variant_id, status, expires_at)`. The order management index begins with `(payment_status, fulfillment_status, created_at DESC, id DESC)`. Search indexes cover normalized email/name fields without indexing encrypted DNI/CUIT plaintext.

- [ ] **Step 4: Validate migration state and PostgreSQL indexes**

Run: `docker compose run --rm backend python manage.py makemigrations --check --dry-run`

Run: `docker compose run --rm -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql tests/test_postgres_performance_indexes.py`

Expected: no model drift and all required index names exist.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/catalog backend/commerce backend/accounts backend/backoffice backend/landing backend/tests/test_postgres_performance_indexes.py
git commit -m "perf: add catalog and management database indexes"
```

### Task 3: SQL-First Catalog Filtering and Database Pagination

**Files:**
- Modify: `backend/catalog/storefront.py`
- Modify: `backend/api_views.py`
- Modify: `backend/catalog/serializers.py`
- Create: `backend/tests/test_catalog_query_performance.py`
- Modify: `backend/tests/test_api_contracts.py`
- Modify: `backend/tests/test_task4_storefront_contracts.py`

**Interfaces:**
- Consumes: query parameters already validated by `ProductListView`, `variant_pricing(ProductVariant)`, and the indexes from Task 2.
- Produces: `CatalogPage` dataclass with `count`, `products`, `snapshots`, `facets`, `next_page`, and `previous_page`; `query_catalog(*, params, attribute_filters, search_requires_query=False) -> CatalogPage`.

- [ ] **Step 1: Write failing behavior and query-budget tests**

```python
def test_catalog_filters_candidates_before_prefetching(api_client, django_assert_max_num_queries):
    with django_assert_max_num_queries(12):
        response = api_client.get(
            "/api/v1/products",
            {"category": "cuadernos", "availability": "in_stock", "page": 2, "page_size": 12},
        )
    assert response.status_code == 200
    assert len(response.data["results"]) <= 12

@pytest.mark.postgresql
def test_search_and_attribute_filters_are_expressed_in_sql(catalog_products):
    candidate_ids = catalog_candidate_queryset(
        params={"query": "cuaderno", "availability": "in_stock"},
        attribute_filters={"color": "azul"},
    )
    sql = str(candidate_ids.query)
    assert "EXISTS" in sql
    assert "to_tsvector" in sql
    assert "LIMIT" not in sql
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `docker compose run --rm backend pytest -q tests/test_catalog_query_performance.py tests/test_api_contracts.py -k catalog`

Expected: failures because the current implementation materializes all candidates and paginates Python lists.

- [ ] **Step 3: Implement SQL candidate filtering**

Create `catalog_candidate_queryset()` that:

- starts with live/sellable products;
- applies category descendants and brand slugs before prefetch;
- uses `Exists` for active variants, current reservations, availability, and each typed attribute filter;
- uses Spanish `SearchVector` plus trigram similarity on PostgreSQL and the current `icontains` fallback on SQLite;
- keeps the commercial promotion calculation authoritative after SQL candidate reduction;
- uses deterministic `(created_at, id)` or `(name, id)` ordering.

The availability annotation must subtract active, unexpired reservations from `on_hand` without invoking `ProductVariant.available_stock` per row.

- [ ] **Step 4: Implement database pagination and bounded commercial fallback**

For default, relevance, and newest ordering without promotion-dependent filters, call `.count()`, slice product IDs in SQL, and only then prefetch variants/media for those IDs. For price, discount, offer, or effective-price range requests, evaluate the already SQL-reduced candidate set, calculate authoritative promotion snapshots, sort/filter, slice IDs, and finally fetch only the requested product page for serialization. Return the existing response envelope unchanged.

- [ ] **Step 5: Remove per-variant reservation queries**

Have `_variant_snapshot()` use a prefetched/annotated `available_stock_value` when present and fall back to `variant.available_stock` only for isolated serializer usage. Ensure the public page does not grow queries as result rows increase.

- [ ] **Step 6: Run catalog contracts and query budgets**

Run: `docker compose run --rm backend pytest -q tests/test_catalog_query_performance.py tests/test_api_contracts.py tests/test_task4_storefront_contracts.py`

Expected: response contracts remain compatible and catalog listing stays within 12 SQL queries.

- [ ] **Step 7: Commit Task 3**

```bash
git add backend/catalog/storefront.py backend/catalog/serializers.py backend/api_views.py backend/tests/test_catalog_query_performance.py backend/tests/test_api_contracts.py backend/tests/test_task4_storefront_contracts.py
git commit -m "perf: filter and paginate catalog in postgresql"
```

### Task 4: Management Query Budgets and Redis Cache Invalidation

**Files:**
- Create: `backend/catalog/cache.py`
- Modify: `backend/catalog/apps.py`
- Modify: `backend/catalog/storefront.py`
- Modify: `backend/api_views.py`
- Modify: `backend/backoffice/catalog_views.py`
- Modify: `backend/backoffice/operations_views.py`
- Modify: `backend/backoffice/access_views.py`
- Modify: `backend/backoffice/content_views.py`
- Modify: `backend/config/settings.py`
- Create: `backend/tests/test_management_query_performance.py`
- Create: `backend/tests/test_catalog_cache.py`

**Interfaces:**
- Consumes: Redis default cache in production and existing catalog/content/promotion models.
- Produces: `catalog_cache_version() -> int`, `bump_catalog_cache_version() -> int`, `catalog_cache_key(namespace: str, payload: Mapping[str, object]) -> str`, and cached serialized facet/category payloads.

- [ ] **Step 1: Write failing query-budget and cache-invalidation tests**

```python
def test_management_product_list_has_constant_query_count(management_client, products):
    with CaptureQueriesContext(connection) as queries:
        response = management_client.get("/api/v1/management/products/?page_size=30")
    assert response.status_code == 200
    assert len(queries) <= 10

def test_product_change_invalidates_catalog_cache(product):
    before = catalog_cache_version()
    product.description = "Nueva descripción"
    product.save()
    assert catalog_cache_version() == before + 1
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `docker compose run --rm backend pytest -q tests/test_management_query_performance.py tests/test_catalog_cache.py`

Expected: management product serialization exceeds the budget and cache version functions are absent.

- [ ] **Step 3: Add production Redis cache and versioned catalog keys**

Configure the default Django cache to use `django.core.cache.backends.redis.RedisCache` when `REDIS_URL` exists and preserve `LocMemCache` for isolated test/development without Redis. Store a numeric catalog version key; build cache keys from sorted, JSON-encoded public filters hashed with SHA-256. Cache serialized facets for 60 seconds and active category payloads for 300 seconds.

- [ ] **Step 4: Add safe invalidation signals**

Register `post_save` and `post_delete` handlers for product, variant, media, category, brand, attribute, promotion, and landing content models. Use `transaction.on_commit(bump_catalog_cache_version)` so rolled-back writes never invalidate and committed writes invalidate exactly once per transaction boundary.

- [ ] **Step 5: Bound management prefetches to list needs**

Split list and detail querysets. Product list prefetches only summarized active variants and primary media; product detail retains complete variants, attributes, stock movements, and media. Order list prefetches only relations consumed by `ManagementOrderSummarySerializer`; order detail retains the full timeline. Customer and audit search use the indexes from Task 2 and preserve database pagination.

- [ ] **Step 6: Run management and cache tests**

Run: `docker compose run --rm backend pytest -q tests/test_management_query_performance.py tests/test_catalog_cache.py tests/test_backoffice_catalog.py tests/test_backoffice_operations.py tests/test_backoffice_access.py`

Expected: primary management lists stay within 10 queries and all write paths invalidate the affected cache namespace.

- [ ] **Step 7: Commit Task 4**

```bash
git add backend/catalog/cache.py backend/catalog/apps.py backend/catalog/storefront.py backend/api_views.py backend/backoffice backend/config/settings.py backend/tests/test_management_query_performance.py backend/tests/test_catalog_cache.py
git commit -m "perf: cache catalog facets and bound management queries"
```

### Task 5: 2 GB Runtime Budget, Pooling Smoke Test, and Operational Documentation

**Files:**
- Modify: `compose.prod.yaml`
- Modify: `.env.production.example`
- Modify: `infra/tests/test_task5b_runtime_boundaries.py`
- Modify: `infra/tests/test_pgbouncer_topology.py`
- Modify: `docs/operations/donweb-production.md`
- Create: `backend/tests/test_postgres_catalog_plans.py`
- Create: `docs/performance/pgbouncer-catalog.md`

**Interfaces:**
- Consumes: completed topology, indexes, query layer, and caching.
- Produces: repeatable commands for `SHOW POOLS`, `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, pool rollback, resource scaling, and production smoke tests.

- [ ] **Step 1: Write failing resource and pooling tests**

```python
def test_initial_memory_defaults_fit_two_gigabyte_vps(rendered_compose):
    expected = {
        "postgres": "384M", "pgbouncer": "32M", "backend": "320M",
        "worker": "256M", "beat": "80M", "redis": "128M",
        "frontend": "256M", "caddy": "64M", "backup": "128M",
    }
    assert {name: memory_limit(rendered_compose, name) for name in expected} == expected

@pytest.mark.postgresql
def test_more_clients_share_fewer_server_connections(pgbouncer_connection_factory):
    clients = pgbouncer_connection_factory(count=24)
    stats = show_pools(clients[0])
    assert stats["cl_active"] + stats["cl_waiting"] >= 24
    assert stats["sv_active"] + stats["sv_idle"] <= 20
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest infra.tests.test_pgbouncer_topology infra.tests.test_task5b_runtime_boundaries -v`

Run: `docker compose run --rm -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql tests/test_postgres_catalog_plans.py`

Expected: current memory defaults exceed the approved values and no PgBouncer concurrency/plan assertions exist.

- [ ] **Step 3: Apply 2 GB service defaults**

Set the exact memory values from the spec, Gunicorn `--workers 2`, and Celery `--concurrency=1`. Preserve existing hardening, health checks, read-only filesystems, and backup serialization. PgBouncer runs non-root under its pinned image and is not published to the host.

- [ ] **Step 4: Add PostgreSQL plan assertions**

Seed enough products, variants, attributes, reservations, orders, and users for the planner to prefer the new indexes. Run `ANALYZE`, then inspect JSON plans for category/newest, brand, fuzzy search, typed attribute, order status, and customer email queries. Assert the expected named index or bitmap index path appears and reject a full sequential scan on the large seeded relation.

- [ ] **Step 5: Execute end-to-end pooling and rollback smoke tests**

Start PostgreSQL, Redis, and PgBouncer; apply migrations directly; then start backend/worker/beat through PgBouncer. Verify `/readyz`, catalog, search, management products, a Celery task, backup dry-run, `SHOW POOLS`, and 24 concurrent clients. Finally render a rollback configuration with `POSTGRES_HOST=postgres` and confirm backend readiness without removing indexes.

- [ ] **Step 6: Document operation and scaling**

Document current pool values, how to inspect `SHOW POOLS`/`SHOW STATS`, warning thresholds (`cl_waiting > 0` sustained or pool saturation), how to increase memory/pool sizes after VPS expansion, direct migration/backup commands, index-plan commands, cache invalidation behavior, and the one-variable rollback.

- [ ] **Step 7: Run the final regression matrix**

Run:

```bash
docker compose run --rm backend ruff check .
docker compose run --rm backend pytest -q
docker compose run --rm -e USE_POSTGRES_TEST_DB=true backend pytest -q -m postgresql
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose config --quiet
docker compose --env-file .env.production.example -f compose.prod.yaml config --quiet
python -m unittest discover -s infra/tests -v
```

Expected: all tests and static/configuration gates pass; credential-gated external provider tests remain explicitly skipped rather than fabricated.

- [ ] **Step 8: Commit Task 5**

```bash
git add compose.prod.yaml .env.production.example infra/tests docs/operations/donweb-production.md docs/performance/pgbouncer-catalog.md backend/tests/test_postgres_catalog_plans.py
git commit -m "docs: operationalize pgbouncer performance on donweb"
```

## Self-Review

- Spec coverage: topology, transaction pooling, direct operational connection, 2 GB limits, SQL-first catalog filtering, dynamic attributes, search, indexes, cache rules, query budgets, measurement, deployment, and rollback each map to Tasks 1-5.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation instruction, or undefined error-handling placeholder remains.
- Type consistency: Task 3 owns `CatalogPage`/`query_catalog`; Task 4 consumes only their serialized facets and defines all cache functions it references; Task 5 consumes named indexes and topology established in Tasks 1-2.
