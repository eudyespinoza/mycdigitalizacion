# Custom Backoffice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar Django Admin por un backoffice propio en `/gestion` que permita operar y configurar toda la tienda.

**Architecture:** El Next.js existente incorporará un área privada modular bajo `/gestion`. Django expondrá contratos staff separados bajo `/api/v1/management/`, reutilizando servicios de dominio, permisos y auditoría; los secretos operativos se almacenarán cifrados y nunca se devolverán.

**Tech Stack:** Next.js 16 App Router, React, TypeScript, Tailwind/CSS existente, Django 5.2 LTS, Django REST Framework, PostgreSQL, Redis, Celery, Fernet, Pytest, Vitest y Playwright.

**Spec:** `docs/superpowers/specs/2026-08-20-custom-backoffice-design.md`

## Global Constraints

- `/admin/` debe responder `404`; ninguna operación depende de Django Admin.
- Toda pantalla y mensaje de negocio debe estar en español.
- Las APIs de gestión exigen usuario interno activo y permisos por acción.
- Los secretos nunca se devuelven; sólo se informa presencia, fecha y actor de rotación.
- Toda escritura sensible es transaccional, auditable e idempotente cuando contacta proveedores.
- El storefront público y sus contratos no deben cambiar.
- Las pantallas deben funcionar con teclado y en 360, 768, 1024 y 1440 px.
- No se considera completa una pantalla alimentada por mocks o datos hardcodeados.

---

### Task 1: Base de `/gestion`, sesión interna y retiro de Django Admin

**Files:**
- Create: `backend/backoffice/__init__.py`
- Create: `backend/backoffice/apps.py`
- Create: `backend/backoffice/permissions.py`
- Create: `backend/backoffice/serializers.py`
- Create: `backend/backoffice/views.py`
- Create: `backend/backoffice/urls.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/api_urls.py`
- Create: `backend/tests/test_backoffice_foundation.py`
- Create: `frontend/app/gestion/layout.tsx`
- Create: `frontend/app/gestion/page.tsx`
- Create: `frontend/components/management/management-shell.tsx`
- Create: `frontend/components/management/management-nav.tsx`
- Create: `frontend/lib/management/types.ts`
- Create: `frontend/lib/management/api.ts`
- Modify: `frontend/app/cuenta/page.tsx`
- Create: `frontend/tests/management-foundation.test.tsx`

**Interfaces:**
- Produces: `IsManagementUser.has_permission(request, view) -> bool`.
- Produces: `GET /api/v1/management/session/ -> ManagementSession`.
- Produces: `GET /api/v1/management/dashboard/ -> ManagementDashboard`.
- Produces: `managementRequest<T>(path, init?) -> Promise<T>`.

- [ ] **Step 1: Write failing backend access tests**

```python
def test_management_session_requires_staff(api_client, customer, staff):
    assert api_client.get("/api/v1/management/session/").status_code == 403
    api_client.force_login(customer)
    assert api_client.get("/api/v1/management/session/").status_code == 403
    api_client.force_login(staff)
    response = api_client.get("/api/v1/management/session/")
    assert response.status_code == 200
    assert response.json()["user"]["is_staff"] is True


def test_django_admin_is_not_routable(client):
    assert client.get("/admin/").status_code == 404
```

- [ ] **Step 2: Run the focused backend test and confirm RED**

Run: `docker compose run --rm backend pytest tests/test_backoffice_foundation.py -q`
Expected: FAIL because the management route does not exist and `/admin/` is still registered.

- [ ] **Step 3: Add the staff permission and session/dashboard contracts**

```python
class IsManagementUser(BasePermission):
    message = "No tenés permiso para acceder al panel de gestión."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)
```

`ManagementSessionSerializer` returns `id`, `email`, `first_name`, `last_name`, `is_staff`, `is_superuser`, `permissions`. `DashboardView` returns counts for orders requiring attention, low-stock variants, active products and integration incidents.

- [ ] **Step 4: Remove all Django Admin URL registrations**

`backend/config/urls.py` keeps health, readiness, API and schema routes only. `django.contrib.admin` and `AdminTwoFactorGateMiddleware` are removed after management authentication tests prove parity. Existing `admin.py` files are not imported by production and will be deleted in Task 6 after all flows migrate.

- [ ] **Step 5: Write failing frontend shell tests**

```tsx
it("muestra navegación operativa y no enlaza Django Admin", async () => {
  render(<ManagementShell session={staffSession}><div>Inicio</div></ManagementShell>);
  expect(screen.getByRole("link", { name: "Catálogo" })).toHaveAttribute("href", "/gestion/catalogo");
  expect(screen.queryByRole("link", { name: /django|admin/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 6: Implement the server-protected management layout**

`/gestion/layout.tsx` obtains the session on the server, redirects anonymous users to `/cuenta/ingresar?next=/gestion`, renders an explicit forbidden screen for authenticated non-staff users, and mounts `ManagementShell` only for staff.

- [ ] **Step 7: Replace the account shortcut**

Staff accounts link to `/gestion`, label the action `Abrir gestión` and never show `/admin/`.

- [ ] **Step 8: Run foundation gates**

Run: `docker compose run --rm backend pytest tests/test_backoffice_foundation.py -q`
Run: `pnpm --dir frontend test:ci -- management-foundation.test.tsx`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/backoffice backend/config/settings.py backend/config/urls.py backend/api_urls.py backend/tests/test_backoffice_foundation.py frontend/app/gestion frontend/components/management frontend/lib/management frontend/app/cuenta/page.tsx frontend/tests/management-foundation.test.tsx
git commit -m "feat: add custom management foundation"
```

---

### Task 2: Configuración general e integraciones cifradas

**Files:**
- Create: `backend/backoffice/models.py`
- Create: `backend/backoffice/secrets.py`
- Create: `backend/backoffice/integrations.py`
- Create: `backend/backoffice/migrations/0001_initial.py`
- Modify: `backend/backoffice/serializers.py`
- Modify: `backend/backoffice/views.py`
- Modify: `backend/backoffice/urls.py`
- Modify: `backend/commerce/provider_config.py`
- Modify: `backend/config/settings.py`
- Create: `backend/tests/test_backoffice_integrations.py`
- Create: `frontend/app/gestion/configuracion/page.tsx`
- Create: `frontend/app/gestion/integraciones/page.tsx`
- Create: `frontend/app/gestion/integraciones/[provider]/page.tsx`
- Create: `frontend/components/management/settings-form.tsx`
- Create: `frontend/components/management/integration-form.tsx`
- Create: `frontend/tests/management-integrations.test.tsx`

**Interfaces:**
- Produces: `IntegrationConfiguration(provider, enabled, environment, public_config, sealed_secrets, version, updated_by)`.
- Produces: `seal_secret_map(values: dict[str, str]) -> str` and `unseal_secret_map(ciphertext: str) -> dict[str, str]`.
- Produces: `GET/PATCH /api/v1/management/integrations/{provider}/`.
- Produces: `POST /api/v1/management/integrations/{provider}/test/`.
- Produces: `GET/PATCH /api/v1/management/settings/general/`.

- [ ] **Step 1: Write RED tests for non-disclosure, encryption and rotation**

```python
def test_mercadopago_secret_is_write_only(staff_client, settings):
    payload = {
        "enabled": True,
        "environment": "sandbox",
        "public_config": {"collector_id": "123"},
        "secrets": {"access_token": "TEST-secret", "webhook_secret": "hook-secret"},
    }
    saved = staff_client.patch("/api/v1/management/integrations/mercadopago/", payload, format="json")
    assert saved.status_code == 200
    assert saved.json()["secret_fields"] == {"access_token": True, "webhook_secret": True}
    assert "TEST-secret" not in str(saved.json())
    row = IntegrationConfiguration.objects.get(provider="mercadopago")
    assert "TEST-secret" not in row.sealed_secrets
```

- [ ] **Step 2: Run and confirm RED**

Run: `docker compose run --rm backend pytest tests/test_backoffice_integrations.py -q`
Expected: FAIL because model and route are missing.

- [ ] **Step 3: Implement encrypted persistence**

Derive a Fernet key from `CONFIG_ENCRYPTION_MASTER_KEY` with SHA-256 and URL-safe Base64. Require the master key in production; in development/test derive from `PERSONAL_DATA_ENCRYPTION_KEY`. Never add secret values to serializer output, exceptions or audit metadata.

- [ ] **Step 4: Implement provider schemas**

Define allow-listed fields for `mercadopago`, `correo_argentino`, `sid_renaper`, `smtp`, `geolocation` and `backups`. Reject unknown fields. An empty secret field preserves the previous value; `clear_secret_fields` explicitly removes selected values.

- [ ] **Step 5: Make provider resolution prefer active DB configuration**

`commerce.provider_config` resolves active decrypted configuration per request/task and falls back to environment only when no database row exists. Cache public readiness metadata, never decrypted secrets.

- [ ] **Step 6: Implement integration screens**

The list shows human labels, `Configurada|Incompleta|Con error|Deshabilitada`, last update and test result. Editors use password inputs with `Configurada` indicators, save confirmation and a separate `Probar conexión` action.

- [ ] **Step 7: Verify and commit**

Run: `docker compose run --rm backend pytest tests/test_backoffice_integrations.py tests/test_provider_smoke.py -q`
Run: `pnpm --dir frontend test:ci -- management-integrations.test.tsx`
Expected: PASS.

```bash
git add backend/backoffice backend/commerce/provider_config.py backend/config/settings.py backend/tests/test_backoffice_integrations.py frontend/app/gestion/configuracion frontend/app/gestion/integraciones frontend/components/management frontend/tests/management-integrations.test.tsx
git commit -m "feat: add secure integration settings"
```

---

### Task 3: Catálogo e inventario

**Files:**
- Create: `backend/backoffice/catalog_serializers.py`
- Create: `backend/backoffice/catalog_views.py`
- Modify: `backend/backoffice/urls.py`
- Create: `backend/tests/test_backoffice_catalog.py`
- Create: `frontend/app/gestion/catalogo/page.tsx`
- Create: `frontend/app/gestion/catalogo/nuevo/page.tsx`
- Create: `frontend/app/gestion/catalogo/[productId]/page.tsx`
- Create: `frontend/app/gestion/categorias/page.tsx`
- Create: `frontend/app/gestion/inventario/page.tsx`
- Create: `frontend/components/management/product-editor.tsx`
- Create: `frontend/components/management/stock-adjustment-dialog.tsx`
- Create: `frontend/tests/management-catalog.test.tsx`

**Interfaces:**
- Produces: product/category/brand/attribute management viewsets.
- Produces: `POST /management/variants/{id}/adjust-stock/` with `{delta, reason}`.
- Produces: `POST /management/products/import/preview/` and `/commit/`.

- [ ] **Step 1: Write RED permission and domain tests**

Test that Catalog role can edit products but cannot see costs without `catalog.view_product_cost`, stock changes always create `InventoryMovement`, invalid variant dimensions fail by field, and CSV commit is atomic.

- [ ] **Step 2: Run RED tests**

Run: `docker compose run --rm backend pytest tests/test_backoffice_catalog.py -q`.

- [ ] **Step 3: Add catalog management serializers and viewsets**

Use nested write serializers for variants and attributes, a dedicated media reorder action, explicit cost permission, optimistic `version`, and existing `catalog.admin_io` import/export services renamed to domain-neutral modules.

- [ ] **Step 4: Implement catalog and inventory screens**

Provide searchable list, status/stock/category filters, product editor sections, variant matrix, media ordering, category tree, CSV preview and stock adjustment dialog with immutable history.

- [ ] **Step 5: Verify and commit**

Run backend focused tests, frontend focused tests, PostgreSQL inventory concurrency tests and OpenAPI validation. Commit as `feat: add catalog and inventory management`.

---

### Task 4: Pedidos, clientes y logística

**Files:**
- Create: `backend/backoffice/order_serializers.py`
- Create: `backend/backoffice/order_views.py`
- Modify: `backend/backoffice/urls.py`
- Create: `backend/tests/test_backoffice_orders.py`
- Create: `frontend/app/gestion/pedidos/page.tsx`
- Create: `frontend/app/gestion/pedidos/[publicId]/page.tsx`
- Create: `frontend/app/gestion/clientes/page.tsx`
- Create: `frontend/app/gestion/clientes/[customerId]/page.tsx`
- Create: `frontend/app/gestion/envios/page.tsx`
- Create: `frontend/components/management/order-timeline.tsx`
- Create: `frontend/components/management/order-action-dialog.tsx`
- Create: `frontend/tests/management-orders.test.tsx`

**Interfaces:**
- Produces: paginated order/customer management endpoints.
- Produces: `POST /management/orders/{public_id}/actions/` with `{action, reason, idempotency_key}`.
- Produces: masked fiscal/identity output and audited reveal endpoint.

- [ ] **Step 1: Write RED workflow tests**

Cover role denial, cancellation matrix, refund idempotency, late payment, shipment retry, manual identity approval, masked data and audited reauthentication-required reveal.

- [ ] **Step 2: Implement APIs using existing domain services**

Delegate to `perform_order_admin_action`, inventory, shipment and identity services. Return stable Spanish codes and never expose `staff_diagnostics` directly.

- [ ] **Step 3: Implement operational screens**

Build filters, attention queue, order timeline, action confirmations, package/tracking view, customer history and masked fiscal data.

- [ ] **Step 4: Verify and commit**

Run focused SQLite tests, live PostgreSQL idempotency/concurrency tests, frontend tests and order E2E. Commit as `feat: add order customer and logistics management`.

---

### Task 5: Landing, promociones y vista previa

**Files:**
- Create: `backend/backoffice/content_serializers.py`
- Create: `backend/backoffice/content_views.py`
- Modify: `backend/backoffice/urls.py`
- Create: `backend/tests/test_backoffice_content.py`
- Create: `frontend/app/gestion/contenido/page.tsx`
- Create: `frontend/app/gestion/contenido/[contentType]/page.tsx`
- Create: `frontend/app/gestion/promociones/page.tsx`
- Create: `frontend/components/management/campaign-editor.tsx`
- Create: `frontend/components/management/content-preview.tsx`
- Create: `frontend/tests/management-content.test.tsx`

**Interfaces:**
- Produces: SiteSettings, hero, promotion slide, collection and popup management endpoints.
- Produces: promotion/coupon CRUD and simulation endpoint.
- Produces: signed staff preview URLs with short expiry.

- [ ] **Step 1: Write RED scheduling/media/permission tests**

Cover desktop/mobile image validation, alt text, focal point, safe heights, order uniqueness, schedules, popup version/frequency, preview permissions and promotion simulation.

- [ ] **Step 2: Implement content and promotion APIs**

Reuse media derivative generation and promotion pricing services. Ensure replacement cleanup is transactional and preview never publishes drafts.

- [ ] **Step 3: Implement visual editors**

Provide reordering, duplicate, enable/disable, date scheduling, breakpoint controls, image focal preview and storefront-sized preview in a new tab.

- [ ] **Step 4: Verify and commit**

Run content/media backend tests, frontend component tests, four-viewport Playwright and axe. Commit as `feat: add content and promotion management`.

---

### Task 6: Roles, auditoría, exports y cierre definitivo

**Files:**
- Create: `backend/backoffice/audit.py`
- Create: `backend/backoffice/user_serializers.py`
- Create: `backend/backoffice/user_views.py`
- Modify: `backend/backoffice/urls.py`
- Modify: `backend/config/settings.py`
- Delete: `backend/catalog/admin.py`
- Delete: `backend/commerce/admin.py`
- Delete: `backend/landing/admin.py`
- Delete: `backend/config/admin_security.py`
- Delete: `backend/templates/admin/**`
- Delete: `backend/static/admin/**`
- Create: `backend/tests/test_backoffice_closure.py`
- Create: `frontend/app/gestion/usuarios/page.tsx`
- Create: `frontend/app/gestion/auditoria/page.tsx`
- Create: `frontend/tests/management-closure.test.tsx`
- Create: `frontend/tests/e2e/management.spec.ts`

**Interfaces:**
- Produces: staff user/role management endpoints.
- Produces: immutable audit list/export endpoints.
- Produces: safe CSV/XLSX exports with formula neutralization.

- [ ] **Step 1: Write closure RED tests**

Assert role matrices, 2FA requirement for Owner, audit append-only behavior, safe exports, `/admin/` 404, no HTML admin templates collected and no frontend `/admin/` links.

- [ ] **Step 2: Implement users, roles and audit screens**

Use existing Django groups and permissions, prevent removal of the last active Propietario, require recent reauthentication for privilege changes, and display audit events with filters and safe detail.

- [ ] **Step 3: Delete obsolete Django Admin implementation**

Remove Admin modules, templates, static assets, middleware and settings dependencies only after parity tests for every operation pass.

- [ ] **Step 4: Run complete verification**

Run: backend full SQLite suite; PostgreSQL marked suite; Ruff; Django check/deploy check; migrations drift; OpenAPI validation; frontend frozen install, lint, typecheck, Vitest and production build; Playwright at 360/768/1024/1440; axe; Compose dev/prod render; Caddy validation.

- [ ] **Step 5: Commit**

```bash
git add backend frontend docs
git commit -m "feat: complete custom management backoffice"
```
