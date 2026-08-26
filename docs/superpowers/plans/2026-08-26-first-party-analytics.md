# First-Party Ecommerce Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build privacy-conscious first-party web analytics plus actionable purchasing and sales dashboards inside Administración.

**Architecture:** A focused Django `analytics` app owns anonymous sessions, allowlisted events, order attribution, conversions, daily aggregates, management selectors and retention tasks. Commerce remains the source of truth for payments, refunds, costs and inventory; Next.js renders server-fetched dashboards while a small client boundary records public navigation without blocking commerce.

**Tech Stack:** Django 5.2, Django REST Framework, PostgreSQL, Redis, Celery, Next.js 16 App Router, React 19, TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-26-first-party-analytics-design.md`

## Global Constraints

- All periods use `[from, to)` in `America/Buenos_Aires`.
- No IP, geolocation, direct identity field, full user-agent or sensitive query string may be persisted in analytics.
- Public analytics failures must never block storefront, cart, checkout or payment.
- The public event catalog is exactly `page_view`, `product_view`, `add_to_cart`, `checkout_started`, `delivery_selected`, and `payment_started`.
- Raw events live 90 days; sessions and daily aggregates live 24 months.
- Orders and payments are the source of commercial truth; browser events never confirm revenue.
- Existing order items with unknown historical cost remain null and are excluded from margin coverage.
- Both new screens inherit global theme variables and mode `Operate`; no fixed brand colors are introduced.
- Interactive filters live in the URL and must not reload the Administración shell.
- Implement with TDD and preserve the untracked user-owned `marketing/` directory.

---

### Task 1: Analytics schema and immutable cost snapshots

**Files:**
- Create: `backend/analytics/__init__.py`
- Create: `backend/analytics/apps.py`
- Create: `backend/analytics/models.py`
- Create: `backend/analytics/migrations/0001_initial.py`
- Create: `backend/commerce/migrations/0021_orderitem_unit_cost_snapshot.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/commerce/models.py`
- Modify: `backend/commerce/services.py`
- Test: `backend/tests/test_analytics_models.py`

**Interfaces:**
- Produces: `AnalyticsSession`, `AnalyticsEvent`, `AnalyticsOrderAttribution`, `AnalyticsConversion`, `AnalyticsDailyProduct`, `AnalyticsDailyChannel`.
- Produces: nullable `OrderItem.unit_cost_snapshot: Decimal | None`, required for all newly-created items.

- [ ] **Step 1: Write failing model and order snapshot tests**

```python
def test_new_order_items_snapshot_variant_cost(order_factory, variant):
    variant.cost = Decimal("1250.00")
    variant.save(update_fields=("cost",))
    order = order_factory(variant=variant)
    assert order.items.get().unit_cost_snapshot == Decimal("1250.00")


def test_analytics_session_does_not_store_identity_fields():
    names = {field.name for field in AnalyticsSession._meta.fields}
    assert names.isdisjoint({"user", "email", "ip", "user_agent"})
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_analytics_models.py -q` from `backend/`
Expected: import/model failures because `analytics` and `unit_cost_snapshot` do not exist.

- [ ] **Step 3: Add focused models and settings**

```python
class AnalyticsSession(models.Model):
    public_id = models.UUIDField(unique=True, editable=False)
    visitor_hash = models.CharField(max_length=64, db_index=True)
    started_at = models.DateTimeField(db_index=True)
    last_seen_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=80, blank=True)
    campaign = models.CharField(max_length=120, blank=True)
    referrer_domain = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=16, default="unknown")
    entry_path = models.CharField(max_length=255)
    viewed_product = models.BooleanField(default=False)
    added_to_cart = models.BooleanField(default=False)
    started_checkout = models.BooleanField(default=False)
    selected_delivery = models.BooleanField(default=False)
    started_payment = models.BooleanField(default=False)
    first_converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = (
            ("view_web_analytics", "Can view web analytics"),
            ("view_commercial_analytics", "Can view commercial analytics"),
            ("export_commercial_analytics", "Can export commercial analytics"),
        )
```

Add one-to-one order attribution, idempotent conversion, strict event choices and daily tables with the indexes defined by the spec. Add `analytics` to `INSTALLED_APPS`, cookie ages and retention settings. Generate migrations with `python manage.py makemigrations analytics commerce` and inspect them before committing.

- [ ] **Step 4: Snapshot variant cost in the existing order transaction**

```python
OrderItem.objects.create(
    order=order,
    variant=line.variant,
    unit_cost_snapshot=line.variant.cost,
    # existing immutable snapshots remain unchanged
)
```

- [ ] **Step 5: Run tests and migration checks**

Run: `python -m pytest tests/test_analytics_models.py tests/test_commerce_round1.py -q`
Run: `python manage.py makemigrations --check --dry-run`
Expected: PASS and `No changes detected`.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics backend/commerce/models.py backend/commerce/services.py backend/commerce/migrations backend/config/settings.py backend/tests/test_analytics_models.py
git commit -m "feat: add analytics schema and cost snapshots"
```

### Task 2: Anonymous session resolution and public event capture

**Files:**
- Create: `backend/analytics/hashing.py`
- Create: `backend/analytics/services.py`
- Create: `backend/analytics/serializers.py`
- Create: `backend/analytics/views.py`
- Create: `backend/analytics/urls.py`
- Modify: `backend/api_urls.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_analytics_capture.py`

**Interfaces:**
- Produces: `TrackingContext(session: AnalyticsSession, visitor_token: str, session_token: str, set_visitor_cookie: bool, set_session_cookie: bool)`.
- Produces: `resolve_tracking_context(request, *, path: str, at=None) -> TrackingContext | None`.
- Produces: `record_event(context, *, event_id, event_type, product=None, variant=None, path="", quantity=None, dimensions=None) -> AnalyticsEvent`.
- Produces: `POST /api/v1/analytics/events/` accepting `{events: AnalyticsEventInput[]}` with at most 20 entries.

- [ ] **Step 1: Write failing privacy, rotation, validation and idempotency tests**

```python
def test_session_rotates_after_thirty_minutes(api_client, freezer):
    first = post_page_view(api_client, event_id=uuid.uuid4())
    freezer.tick(delta=timedelta(minutes=31))
    second = post_page_view(api_client, event_id=uuid.uuid4())
    assert second.cookies[settings.ANALYTICS_SESSION_COOKIE_NAME].value != first.cookies[settings.ANALYTICS_SESSION_COOKIE_NAME].value


def test_event_id_is_idempotent(api_client, event_payload):
    assert api_client.post("/api/v1/analytics/events/", event_payload, format="json").status_code == 202
    assert api_client.post("/api/v1/analytics/events/", event_payload, format="json").status_code == 202
    assert AnalyticsEvent.objects.count() == 1
```

Also assert that `/gestion`, `/healthz`, unknown event names, unknown dimensions, oversized batches and sensitive paths are excluded or rejected as specified.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_analytics_capture.py -q`
Expected: 404 for the endpoint and missing service imports.

- [ ] **Step 3: Implement HMAC tokens and allowlisted input**

```python
def token_hash(token: str) -> str:
    return hmac.new(settings.ANALYTICS_HMAC_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


class AnalyticsEventInputSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    event_type = serializers.ChoiceField(choices=AnalyticsEvent.EventType.values)
    path = serializers.CharField(max_length=255, required=False, allow_blank=True)
    product_id = serializers.IntegerField(required=False, min_value=1)
    variant_id = serializers.IntegerField(required=False, min_value=1)
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=1000)
```

Normalize routes, UTM values and referrer hostname before persistence. Classify devices without retaining the raw user-agent. Apply the `analytics_event` throttle and return `202 {"accepted": n}`.

- [ ] **Step 4: Set cookies only on successful accepted events**

Use `httponly=True`, `secure=settings.ANALYTICS_COOKIE_SECURE`, `samesite="Lax"`, path `/`, and the configured ages. Never log tokens or payload content.

- [ ] **Step 5: Run capture and security regression tests**

Run: `python -m pytest tests/test_analytics_capture.py tests/test_security_round1.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics backend/api_urls.py backend/config/settings.py backend/tests/test_analytics_capture.py
git commit -m "feat: capture anonymous commerce events"
```

### Task 3: Commerce attribution and server-authoritative conversions

**Files:**
- Modify: `backend/analytics/services.py`
- Modify: `backend/api_views.py`
- Modify: `backend/commerce/payments.py`
- Modify: `backend/commerce/tasks.py`
- Test: `backend/tests/test_analytics_commerce.py`

**Interfaces:**
- Produces: `link_order_to_request_session(request, order) -> AnalyticsOrderAttribution | None`.
- Produces: `record_paid_conversion(*, order, transaction) -> AnalyticsConversion | None`.
- Produces: `record_refund_change(*, refund) -> None`, which invalidates commercial caches without creating a fake browser event.

- [ ] **Step 1: Write failing server-boundary tests**

```python
def test_paid_webhook_creates_one_conversion_for_repeated_processing(attributed_order, approved_payload):
    apply_payment_status(attributed_order.transaction, approved_payload)
    apply_payment_status(attributed_order.transaction, approved_payload)
    assert AnalyticsConversion.objects.filter(order=attributed_order.order).count() == 1


def test_checkout_without_analytics_cookie_still_completes(client, checkout_payload):
    response = client.post("/api/v1/checkout/", checkout_payload, content_type="application/json")
    assert response.status_code in {201, 202}
    assert not AnalyticsOrderAttribution.objects.exists()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_analytics_commerce.py -q`
Expected: missing attribution/conversion services.

- [ ] **Step 3: Instrument successful cart and checkout boundaries**

After `add_cart_line` succeeds, record `add_to_cart` using the request session. After `confirm_checkout`, link the order, set `started_checkout`, `selected_delivery`, and `started_payment` from server-confirmed state. Resume checkout reuses the same attribution and never creates a second link.

```python
result = confirm_checkout(
    cart=get_or_create_user_cart(user=request.user),
    user=request.user,
    fulfillment_method=values["fulfillment_method"],
    sid_adapter=get_sid_adapter(),
    payment_adapter=get_payment_adapter(),
    address=address,
    shipping_quote=quote,
    billing_profile=billing_profile,
    consent=values["consent"],
    idempotency_key=values["idempotency_key"],
)
link_order_to_request_session(request, result.order)
mark_checkout_state(request, order=result.order, fulfillment_method=values["fulfillment_method"], payment_started=result.transaction is not None)
```

- [ ] **Step 4: Create conversion at payment approval**

Call `record_paid_conversion` only after the approved `PaymentTransaction` and paid order transition commit. Register `transaction.on_commit(lambda: record_paid_conversion(order=order, transaction=payment_transaction), robust=True)` so analytics can never roll back or surface as a payment failure. Repeated webhooks return the existing row by the unique order constraint.

- [ ] **Step 5: Verify commerce cannot be broken by analytics errors**

Patch each analytics service to raise and assert cart/checkout/payment remain successful while the failure is logged only as an operational diagnostic without tokens or PII.

Run: `python -m pytest tests/test_analytics_commerce.py tests/test_postgres_checkout.py tests/test_task3_round2_regressions.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics/services.py backend/api_views.py backend/commerce/payments.py backend/commerce/tasks.py backend/tests/test_analytics_commerce.py
git commit -m "feat: attribute paid orders to analytics sessions"
```

### Task 4: Daily rollups, retention and cache invalidation

**Files:**
- Create: `backend/analytics/tasks.py`
- Create: `backend/analytics/selectors.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_analytics_tasks.py`

**Interfaces:**
- Produces: `rollup_analytics_day(day: date) -> RollupResult`.
- Produces: Celery tasks `analytics.tasks.reconcile_missing_conversions`, `analytics.tasks.rollup_recent_analytics` and `analytics.tasks.purge_expired_analytics`.
- Produces: `invalidate_web_analytics()` and `invalidate_commercial_analytics()`.

- [ ] **Step 1: Write failing rollup and retention tests**

```python
def test_rollup_is_idempotent(analytics_day_fixture):
    first = rollup_analytics_day(analytics_day_fixture.day)
    second = rollup_analytics_day(analytics_day_fixture.day)
    assert first == second
    assert AnalyticsDailyProduct.objects.count() == analytics_day_fixture.expected_products


def test_retention_keeps_sessions_longer_than_events(now):
    purge_expired_analytics(now=now)
    assert not AnalyticsEvent.objects.filter(occurred_at__lt=now - timedelta(days=90)).exists()
    assert AnalyticsSession.objects.filter(started_at__gte=now - timedelta(days=730)).exists()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_analytics_tasks.py -q`.

- [ ] **Step 3: Implement transactional upserts and recent repair window**

Aggregate `AnalyticsDailyProduct` and `AnalyticsDailyChannel` per Argentina date. Delete and recreate only the target day inside one transaction so reruns repair late payments without double counting.

- [ ] **Step 4: Schedule tasks**

Add reconciliation for approved attributed payments missing conversions, a daily rollup that repairs the previous seven local days and a daily purge. Configure cache namespaces with version keys instead of key scans.

- [ ] **Step 5: Run task tests and Celery configuration check**

Run: `python -m pytest tests/test_analytics_tasks.py tests/test_task5b_observability.py -q`
Run: `python manage.py check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics/tasks.py backend/analytics/selectors.py backend/config/settings.py backend/tests/test_analytics_tasks.py
git commit -m "feat: aggregate and retain analytics data"
```

### Task 5: Management analytics APIs, permissions and CSV export

**Files:**
- Create: `backend/analytics/management_serializers.py`
- Create: `backend/analytics/management_views.py`
- Modify: `backend/backoffice/urls.py`
- Modify: `backend/backoffice/permissions.py`
- Modify: `backend/config/admin_roles.py`
- Test: `backend/tests/test_analytics_management.py`
- Test: `backend/tests/test_management_query_performance.py`

**Interfaces:**
- Produces: `web_dashboard(*, start, end, compare) -> dict`.
- Produces: `commercial_dashboard(*, start, end, compare, category_id=None, brand_id=None, coverage_days=30) -> dict`.
- Produces: `GET /api/v1/management/analytics/web/`.
- Produces: `GET /api/v1/management/analytics/commercial/`.
- Produces: `GET /api/v1/management/analytics/commercial/export.csv`.

- [ ] **Step 1: Write failing formula, permission and export tests**

```python
def test_commercial_dashboard_uses_approved_payments_and_refunds(management_client, analytics_sales_fixture):
    response = management_client.get("/api/v1/management/analytics/commercial/?from=2026-08-01&to=2026-09-01")
    assert response.status_code == 200
    assert response.json()["kpis"]["net_sales"] == "87500.00"
    assert response.json()["kpis"]["refunds"] == "12500.00"


def test_margin_reports_cost_coverage_instead_of_estimating(management_client, paid_items_with_partial_cost):
    payload = management_client.get(COMMERCIAL_URL).json()
    assert payload["kpis"]["cost_coverage_percentage"] == "50.00"
```

Cover no denominator, 24-hour mature checkout abandonment, prior-period comparison, timezone boundary, stock infinity, no rotation, 15/30/60-day reorder, empty days, invalid range, and CSV audit.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_analytics_management.py -q`.

- [ ] **Step 3: Implement selectors with stable response contracts**

```python
{
    "period": {"from": "2026-08-01", "to": "2026-09-01", "timezone": "America/Buenos_Aires"},
    "data_since": "2026-08-26T00:00:00-03:00",
    "coverage": {"attribution_percentage": "93.40", "cost_percentage": "84.20"},
    "kpis": {"sessions": 120, "conversion_rate": "3.50", "net_sales": "87500.00"},
    "series": [{"date": "2026-08-01", "sessions": 12, "orders": 1, "net_sales": "12500.00"}],
    "tables": {"products": [], "channels": [], "reorder": []},
}
```

Return `null` plus `has_denominator: false` for undefined rates. Use `PaymentTransaction.approved_at` and approved `Refund.updated_at`, not current order state or order creation time.

- [ ] **Step 4: Apply exact role permissions**

Add a reusable permission class taking `required_permission`. Synchronize Owner, Content, Catalog and Orders/Logistics exactly as the spec states. Hide no data only at serialization; authorization must occur before selectors execute.

- [ ] **Step 5: Implement audited CSV export**

Stream UTF-8 with BOM and Argentine-readable headings. Export aggregated SKU rows only, never sessions, customers or identifiable orders. Record actor, period, filters and row count in `ManagementAuditEvent`.

- [ ] **Step 6: Verify APIs and query budgets**

Run: `python -m pytest tests/test_analytics_management.py tests/test_management_query_performance.py tests/test_backoffice_foundation.py -q`
Expected: PASS within explicit query ceilings.

- [ ] **Step 7: Commit**

```bash
git add backend/analytics backend/backoffice/urls.py backend/backoffice/permissions.py backend/config/admin_roles.py backend/tests/test_analytics_management.py backend/tests/test_management_query_performance.py
git commit -m "feat: expose management analytics reports"
```

### Task 6: Storefront tracker and successful-action instrumentation

**Files:**
- Create: `frontend/lib/analytics/types.ts`
- Create: `frontend/lib/analytics/client.ts`
- Create: `frontend/components/analytics/analytics-tracker.tsx`
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/components/analytics/product-view-tracker.tsx`
- Modify: `frontend/app/producto/[slug]/page.tsx`
- Test: `frontend/tests/analytics-tracker.test.tsx`

**Interfaces:**
- Produces: `trackAnalytics(event: AnalyticsClientEvent): Promise<void>` that always resolves.
- Produces: `<AnalyticsTracker />` listening to pathname changes and sending one `page_view` per normalized navigation.

- [ ] **Step 1: Write failing tracker tests**

```tsx
test("records one page view per App Router navigation", async () => {
  render(<AnalyticsTracker />);
  expect(fetch).toHaveBeenCalledTimes(1);
  navigate("/catalogo?utm_source=instagram");
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});

test("never rejects the commerce action when analytics fails", async () => {
  mockAnalyticsFailure();
  await expect(addProductToCart()).resolves.toBeDefined();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `corepack pnpm exec vitest run tests/analytics-tracker.test.tsx --reporter=dot` from `frontend/`.

- [ ] **Step 3: Implement a deep client boundary**

Use `usePathname` and `useSearchParams` only inside `AnalyticsTracker`; keep `RootLayout` a Server Component and wrap the tracker in `Suspense`. Generate UUIDs in the browser, batch briefly, call `apiRequest("/analytics/events/", { method: "POST", body: JSON.stringify({ events }) })`, and swallow only analytics errors.

- [ ] **Step 4: Instrument product views without duplicating server events**

Emit `product_view` once from product detail. `add_to_cart`, `checkout_started`, `delivery_selected` and `payment_started` remain server-captured by Task 3; document that ownership in `client.ts` and do not emit them from React.

- [ ] **Step 5: Run frontend regressions**

Run: `corepack pnpm exec vitest run tests/analytics-tracker.test.tsx tests/product-card-cart.test.tsx tests/checkout-delivery-options.test.tsx --reporter=dot --silent`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/analytics frontend/components/analytics frontend/app/layout.tsx frontend/app/producto/[slug]/page.tsx frontend/tests/analytics-tracker.test.tsx
git commit -m "feat: instrument the storefront funnel"
```

### Task 7: Shared management analytics UI foundation

**Files:**
- Create: `frontend/lib/management/analytics-types.ts`
- Create: `frontend/lib/management/analytics-filters.ts`
- Create: `frontend/components/management/analytics/analytics-filters.tsx`
- Create: `frontend/components/management/analytics/kpi-grid.tsx`
- Create: `frontend/components/management/analytics/metric-chart.tsx`
- Create: `frontend/components/management/analytics/funnel.tsx`
- Create: `frontend/components/management/analytics/data-table.tsx`
- Modify: `frontend/app/styles.css`
- Test: `frontend/tests/management-analytics-components.test.tsx`

**Interfaces:**
- Produces serializable `WebAnalyticsReport` and `CommercialAnalyticsReport` types matching Task 5.
- Produces `parseAnalyticsFilters(searchParams) -> AnalyticsFilters` and `buildAnalyticsQuery(filters) -> string`.
- Produces accessible chart components that always render a textual/table equivalent.

- [ ] **Step 1: Write failing component and filter tests**

```tsx
test("shows Sin datos instead of a false zero rate", () => {
  render(<KpiGrid items={[{ label: "Conversión", value: null, hasDenominator: false }]} />);
  expect(screen.getByText("Sin datos")).toBeVisible();
});

test("keeps all filters in the URL", () => {
  expect(buildAnalyticsQuery({ from: "2026-08-01", to: "2026-09-01", compare: true, coverageDays: 30 }))
    .toBe("from=2026-08-01&to=2026-09-01&compare=1&coverage_days=30");
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `corepack pnpm exec vitest run tests/management-analytics-components.test.tsx --reporter=dot`.

- [ ] **Step 3: Implement compact themed primitives**

Use CSS/SVG already controlled by project tokens; do not add a chart dependency. Each SVG gets a concise accessible name and a sibling table or summary. Use tabular numerals and explicit units.

- [ ] **Step 4: Add responsive layout rules**

Implement 1440/1024, 768 and 360 layouts with no document-level horizontal overflow. Tables become labelled operational rows on narrow screens; charts keep labels visible.

- [ ] **Step 5: Run component, type and lint checks**

Run: `corepack pnpm exec vitest run tests/management-analytics-components.test.tsx --reporter=dot --silent`
Run: `corepack pnpm run typecheck`
Run: `corepack pnpm run lint`.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/management/analytics-* frontend/components/management/analytics frontend/app/styles.css frontend/tests/management-analytics-components.test.tsx
git commit -m "feat: add accessible analytics UI primitives"
```

### Task 8: Web metrics dashboard

**Files:**
- Create: `frontend/app/gestion/metricas/page.tsx`
- Create: `frontend/components/management/analytics/web-analytics-dashboard.tsx`
- Create: `frontend/app/gestion/metricas/error.tsx`
- Test: `frontend/tests/management-web-analytics.test.tsx`

**Interfaces:**
- Consumes: `GET /management/analytics/web/`, shared filters and primitives.
- Produces: `/gestion/metricas` with KPI, funnel, daily series, product performance, channels, devices and honest states.

- [ ] **Step 1: Write failing dashboard tests**

```tsx
test("renders the full funnel and attribution coverage", () => {
  render(<WebAnalyticsDashboard report={webReportFixture} />);
  expect(screen.getByRole("heading", { name: "Embudo de compra" })).toBeVisible();
  expect(screen.getByText("Cobertura de atribución 93,4 %")).toBeVisible();
});

test("explains when measurement began", () => {
  render(<WebAnalyticsDashboard report={emptyWebReportFixture} />);
  expect(screen.getByText(/medición comenzó/i)).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `corepack pnpm exec vitest run tests/management-web-analytics.test.tsx --reporter=dot`.

- [ ] **Step 3: Implement server page and focused client filters**

Await `searchParams` inside the page, normalize through `parseAnalyticsFilters`, fetch with `managementServerGet`, and pass serializable data into the interactive filters only. Preserve the management shell during navigation.

- [ ] **Step 4: Implement all approved sections and states**

Keep the first viewport compact: heading/filter bar, six KPI, then funnel. Link product rows to `/gestion/catalogo/{id}`. Error state keeps filters and offers retry.

- [ ] **Step 5: Run dashboard tests**

Run: `corepack pnpm exec vitest run tests/management-web-analytics.test.tsx tests/management-analytics-components.test.tsx --reporter=dot --silent`.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/gestion/metricas frontend/components/management/analytics/web-analytics-dashboard.tsx frontend/tests/management-web-analytics.test.tsx
git commit -m "feat: add web metrics dashboard"
```

### Task 9: Purchasing and sales dashboard, navigation and export

**Files:**
- Create: `frontend/app/gestion/estadisticas/page.tsx`
- Create: `frontend/components/management/analytics/commercial-dashboard.tsx`
- Create: `frontend/app/gestion/estadisticas/error.tsx`
- Modify: `frontend/components/management/management-nav.tsx`
- Modify: `frontend/app/gestion/page.tsx`
- Modify: `frontend/lib/management/types.ts`
- Test: `frontend/tests/management-commercial-analytics.test.tsx`
- Test: `frontend/tests/management-foundation.test.tsx`

**Interfaces:**
- Consumes: commercial report endpoint and audited CSV endpoint.
- Produces: `/gestion/estadisticas` and permission-aware links `Métricas web` and `Compras y ventas` immediately after Inicio.

- [ ] **Step 1: Write failing commercial and navigation tests**

```tsx
test("shows margin coverage and reorder rationale", () => {
  render(<CommercialDashboard report={commercialReportFixture} />);
  expect(screen.getByText("Cobertura de costos 84,2 %")).toBeVisible();
  expect(screen.getByRole("columnheader", { name: "Reposición sugerida" })).toBeVisible();
  expect(screen.getByText(/no contempla proveedor ni lote mínimo/i)).toBeVisible();
});

test("navigation exposes analytics only with permission", () => {
  render(<ManagementNav permissions={["analytics.view_web_analytics"]} />);
  expect(screen.getByRole("link", { name: "Métricas web" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Compras y ventas" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `corepack pnpm exec vitest run tests/management-commercial-analytics.test.tsx tests/management-foundation.test.tsx --reporter=dot`.

- [ ] **Step 3: Make navigation permission-aware**

Pass `session.user.permissions` from `ManagementShell` to `ManagementNav`; attach `requiredPermission` to the two new entries. Keep current unread-support behavior and mobile menu intact.

- [ ] **Step 4: Implement commercial dashboard and CSV link**

Render net sales, collected orders, net units, average ticket, discounts, refunds and gross product margin with cost coverage. Add category/SKU performance, inventory value, no-movement list and reorder table. Build export URL from the exact active filters.

- [ ] **Step 5: Verify frontend and accessibility contracts**

Run: `corepack pnpm exec vitest run tests/management-commercial-analytics.test.tsx tests/management-foundation.test.tsx --reporter=dot --silent`
Run: `corepack pnpm run typecheck && corepack pnpm run lint`.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/gestion/estadisticas frontend/components/management/analytics/commercial-dashboard.tsx frontend/components/management/management-nav.tsx frontend/components/management/management-shell.tsx frontend/app/gestion/page.tsx frontend/lib/management/types.ts frontend/tests/management-commercial-analytics.test.tsx frontend/tests/management-foundation.test.tsx
git commit -m "feat: add purchasing and sales analytics"
```

### Task 10: Full verification, visual finish and production rollout

**Files:**
- Modify if required by findings: analytics backend/frontend targets from Tasks 1-9.
- Update: `docs/superpowers/specs/2026-08-26-first-party-analytics-design.md` only if the final implementation establishes a different durable fact.
- Create captures: `.impeccable/review/analytics-desktop.png`
- Create captures: `.impeccable/review/analytics-mobile.png`

**Interfaces:**
- Produces: production-ready migrations, services, two dashboards, tracker, rollups and monitored deployment.

- [ ] **Step 1: Run full backend verification**

Run from `backend/`:

```bash
python -m pytest -q
python -m ruff check .
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
```

Expected: all exit 0; skipped legacy Django Admin contracts remain documented skips only.

- [ ] **Step 2: Run full frontend verification**

Run from `frontend/`:

```bash
corepack pnpm run test:ci -- --reporter=dot --silent
corepack pnpm run typecheck
corepack pnpm run lint
corepack pnpm run build
```

Expected: all exit 0.

- [ ] **Step 3: Load Impeccable craft floor immediately before final UI edits**

Read `C:/Users/edespinoza/.codex/skills/impeccable/reference/craft-floor.md`, capture `/gestion/metricas` and `/gestion/estadisticas` at desktop and mobile in one batch, inspect the files, then fix all material findings in one batch.

- [ ] **Step 4: Run detector and one confirmation capture**

Run:

```bash
node C:/Users/edespinoza/.codex/skills/impeccable/scripts/detect.mjs --json --target frontend/app/gestion/metricas/page.tsx --target frontend/app/gestion/estadisticas/page.tsx
```

Resolve mechanical findings, recapture once, and validate that every capture shows the named screen without loading, overflow or blank regions.

- [ ] **Step 5: Review security and privacy at the boundary**

Inspect database rows and request logs from a synthetic session. Confirm no IP, email, user id, full user-agent, token, full referrer URL or sensitive query parameter appears. Confirm analytics endpoint failure leaves a real cart and checkout successful.

- [ ] **Step 6: Deploy backend-compatible schema first**

Push the verified commit, deploy production containers, run migrations, synchronize roles, and keep tracker disabled until backend health and migration checks pass.

- [ ] **Step 7: Enable capture and validate production canaries**

Enable tracker and Celery schedules, then verify:

- public navigation creates one allowlisted event;
- management metrics show `data_since` without fabricated history;
- a synthetic cart/checkout does not duplicate events;
- existing commerce remains healthy;
- rollup and purge tasks are registered;
- both routes authorize correctly and respond at desktop/mobile widths.

- [ ] **Step 8: Commit any bounded finish corrections**

```bash
git add backend/analytics backend/api_views.py backend/backoffice/permissions.py backend/backoffice/urls.py backend/commerce/models.py backend/commerce/services.py backend/commerce/payments.py backend/config/settings.py backend/config/admin_roles.py frontend/app/layout.tsx frontend/app/styles.css frontend/app/gestion/metricas frontend/app/gestion/estadisticas frontend/app/gestion/page.tsx frontend/app/producto/[slug]/page.tsx frontend/components/analytics frontend/components/management/analytics frontend/components/management/management-nav.tsx frontend/components/management/management-shell.tsx frontend/lib/analytics frontend/lib/management frontend/tests backend/tests
git commit -m "fix: finish first-party analytics dashboards"
```
