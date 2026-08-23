# Support Conversations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build public consultation and problem-report conversations with secure guest recovery, private attachments, configurable-theme UI, and a complete management inbox.

**Architecture:** A new Django `support` app owns cases, messages, guest access, attachment validation, and state transitions. Public REST contracts and private management contracts remain separate while sharing domain services; Next.js adds public routes and an Operate-style management inbox using the existing global theme variables.

**Tech Stack:** Django 5.2, Django REST Framework, PostgreSQL, Celery, Redis, Next.js 16 App Router, React 19, TypeScript, Vitest, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-support-conversations-design.md`

## Global Constraints

- Consultations and problem reports share one case/message/attachment engine.
- Guests work without an account or SMTP through an HttpOnly session cookie plus case number and private recovery code.
- A matching email never claims a case; claiming requires the private code.
- Maximum 5 files per message, 10 MB per file, and 30 MB total.
- Allowed files are JPEG, PNG, WebP, PDF, TXT, CSV, DOCX, and XLSX; public media URLs must never expose originals.
- The public and management UI use `--blue`, `--magenta-action`, `--cyan-action`, `--surface*`, `--ink`, `--muted`, and `--line`; do not hardcode brand colors.
- Forms remain closed until the user explicitly requests creation or recovery.
- All visible copy is Spanish (Argentina), WCAG 2.2 AA, keyboard usable, reduced-motion safe, and verified at 360, 768, 1024, and 1440 px.
- Every production behavior starts with a failing test and follows red-green-refactor.

---

### Task 1: Support domain and guest access

**Files:**
- Create: `backend/support/__init__.py`
- Create: `backend/support/apps.py`
- Create: `backend/support/models.py`
- Create: `backend/support/access.py`
- Create: `backend/support/migrations/0001_initial.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_support_domain.py`

**Interfaces:**
- Produces: `SupportCase`, `SupportMessage`, `SupportAttachment`, `SupportGuestSession`, `SupportGuestAccess`.
- Produces: `issue_guest_session() -> tuple[SupportGuestSession, str]`, `resolve_guest_session(raw_token: str) -> SupportGuestSession | None`, and `verify_recovery_code(case, raw_code) -> bool`.
- Consumes: `accounts.User`, `commerce.Order`, `catalog.Product`.

- [ ] **Step 1: Write failing model and token tests**

```python
def test_guest_token_is_stored_as_a_hash():
    session, raw_token = issue_guest_session()
    assert raw_token not in session.token_hash
    assert resolve_guest_session(raw_token) == session


def test_case_number_and_recovery_code_are_non_sequential_and_private():
    case, raw_code = create_case_with_recovery(subject="Consulta por cuadernos")
    assert case.case_number.startswith("CON-")
    assert raw_code not in case.recovery_code_hash
    assert verify_recovery_code(case, raw_code)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend; pytest tests/test_support_domain.py -q`
Expected: collection fails because `support.models` and `support.access` do not exist.

- [ ] **Step 3: Implement focused models and access helpers**

```python
class SupportCase(models.Model):
    class Kind(models.TextChoices):
        CONSULTATION = "consultation", "Consulta"
        PROBLEM = "problem", "Problema"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case_number = models.CharField(max_length=24, unique=True, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    subject = models.CharField(max_length=180)
    category = models.CharField(max_length=32)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    recovery_code_hash = models.CharField(max_length=128)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)


def issue_guest_session():
    raw = secrets.token_urlsafe(32)
    session = SupportGuestSession.objects.create(token_hash=make_password(raw))
    return session, raw


def resolve_guest_session(raw_token):
    for session in SupportGuestSession.objects.filter(revoked_at__isnull=True):
        if check_password(raw_token, session.token_hash):
            return session
    return None
```

Use a keyed digest lookup column in addition to the slow password hash so resolution performs one indexed query rather than scanning sessions.

- [ ] **Step 4: Add app registration and migration**

Add `"support"` to `INSTALLED_APPS`, create indexes from the specification, and apply the migration.

Run: `cd backend; python manage.py migrate`

- [ ] **Step 5: Run domain tests and commit**

Run: `cd backend; pytest tests/test_support_domain.py -q`
Expected: PASS.

```bash
git add backend/support backend/config/settings.py backend/tests/test_support_domain.py
git commit -m "feat: add support conversation domain"
```

### Task 2: Case services, state transitions, and attachment security

**Files:**
- Create: `backend/support/services.py`
- Create: `backend/support/attachments.py`
- Create: `backend/support/storage.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_support_services.py`
- Test: `backend/tests/test_support_attachments.py`

**Interfaces:**
- Consumes: Task 1 models and access helpers.
- Produces: `create_case(actor, guest_session, payload, files, idempotency_key) -> CaseCreationResult`.
- Produces: `append_message(case, actor, role, body, files, idempotency_key) -> SupportMessage`.
- Produces: `transition_after_message(case, role) -> None` and `claim_case(case, user, recovery_code) -> SupportCase`.
- Produces: `validate_support_files(files) -> list[ValidatedUpload]`.

- [ ] **Step 1: Write failing service tests**

```python
def test_staff_and_customer_messages_drive_waiting_state(case, staff, customer):
    append_message(case, staff, "staff", "¿Podés enviar una foto?", [], "staff-1")
    assert case.status == SupportCase.Status.WAITING_CUSTOMER
    append_message(case, customer, "customer", "Adjunto la foto", [], "customer-1")
    assert case.status == SupportCase.Status.WAITING_STAFF


def test_message_idempotency_prevents_duplicate(case, customer):
    first = append_message(case, customer, "customer", "Hola", [], "same-key")
    second = append_message(case, customer, "customer", "Hola", [], "same-key")
    assert first.pk == second.pk
    assert case.messages.count() == 1
```

- [ ] **Step 2: Write failing attachment tests**

```python
def test_rejects_executable_disguised_as_png(uploaded_file):
    uploaded_file.name = "captura.png"
    uploaded_file.file.write(b"MZ" + b"0" * 30)
    with pytest.raises(AttachmentValidationError):
        validate_support_files([uploaded_file])


def test_rejects_more_than_five_files(valid_pngs):
    with pytest.raises(AttachmentValidationError, match="Hasta 5 archivos"):
        validate_support_files(valid_pngs[:6])
```

- [ ] **Step 3: Run both files and verify RED**

Run: `cd backend; pytest tests/test_support_services.py tests/test_support_attachments.py -q`
Expected: FAIL because the services and validators are missing.

- [ ] **Step 4: Implement transactional services and validation**

```python
@transaction.atomic
def append_message(*, case, actor, role, body, files, idempotency_key):
    existing = SupportMessage.objects.filter(case=case, idempotency_key=idempotency_key).first()
    if existing:
        return existing
    validated = validate_support_files(files)
    message = SupportMessage.objects.create(case=case, author=actor, author_role=role, body=body.strip(), idempotency_key=idempotency_key)
    persist_validated_uploads(message, validated)
    transition_after_message(case, role)
    return message
```

Private files use `SUPPORT_PRIVATE_MEDIA_ROOT`; image previews are decoded and regenerated before inline display. All other downloads use attachment disposition and `nosniff`.

- [ ] **Step 5: Run service tests and commit**

Run: `cd backend; pytest tests/test_support_services.py tests/test_support_attachments.py -q`
Expected: PASS.

```bash
git add backend/support backend/config/settings.py backend/tests/test_support_services.py backend/tests/test_support_attachments.py
git commit -m "feat: secure support messages and attachments"
```

### Task 3: Public support API

**Files:**
- Create: `backend/support/serializers.py`
- Create: `backend/support/permissions.py`
- Create: `backend/support/views.py`
- Create: `backend/support/urls.py`
- Modify: `backend/api_urls.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_support_api.py`

**Interfaces:**
- Consumes: Task 2 services.
- Produces the `/api/v1/support/` contracts from the specification.
- Produces cookie name `myc_support_session` and response field `recovery_code` only on first successful creation.

- [ ] **Step 1: Write failing guest creation and isolation tests**

```python
def test_guest_creates_case_and_continues_with_secure_cookie(api_client):
    response = api_client.post("/api/v1/support/cases/", guest_payload(), format="multipart")
    assert response.status_code == 201
    assert response.json()["recovery_code"]
    assert response.cookies["myc_support_session"]["httponly"]
    listed = api_client.get("/api/v1/support/cases/")
    assert listed.json()["results"][0]["public_id"] == response.json()["public_id"]


def test_other_session_cannot_read_or_download_case(api_client, guest_case):
    assert api_client.get(f"/api/v1/support/cases/{guest_case.public_id}/").status_code == 404
```

- [ ] **Step 2: Write failing recovery and claim tests**

```python
def test_recovery_requires_number_and_private_code(api_client, guest_case_and_code):
    case, code = guest_case_and_code
    denied = api_client.post("/api/v1/support/access/", {"case_number": case.case_number, "code": "wrong"}, format="json")
    assert denied.status_code == 400
    allowed = api_client.post("/api/v1/support/access/", {"case_number": case.case_number, "code": code}, format="json")
    assert allowed.status_code == 200
```

- [ ] **Step 3: Run API tests and verify RED**

Run: `cd backend; pytest tests/test_support_api.py -q`
Expected: 404 for missing support routes.

- [ ] **Step 4: Implement serializers, object permission, cookies, throttles, and private download**

```python
urlpatterns = [
    path("configuration/", SupportConfigurationView.as_view()),
    path("cases/", SupportCaseListCreateView.as_view()),
    path("cases/<uuid:public_id>/", SupportCaseDetailView.as_view()),
    path("cases/<uuid:public_id>/messages/", SupportMessageCreateView.as_view()),
    path("cases/<uuid:public_id>/claim/", SupportCaseClaimView.as_view()),
    path("access/", SupportAccessView.as_view()),
    path("attachments/<uuid:public_id>/", SupportAttachmentDownloadView.as_view()),
]
```

Return 404 rather than 403 for inaccessible case IDs. Sanitize `source_url` by storing path and origin only.

- [ ] **Step 5: Run API and OpenAPI tests and commit**

Run: `cd backend; pytest tests/test_support_api.py tests/test_openapi_semantics.py -q`
Expected: PASS.

```bash
git add backend/support backend/api_urls.py backend/config/settings.py backend/tests/test_support_api.py
git commit -m "feat: expose public support API"
```

### Task 4: Management inbox, permissions, audit, and notifications

**Files:**
- Create: `backend/support/management_serializers.py`
- Create: `backend/support/management_views.py`
- Create: `backend/support/tasks.py`
- Create: `backend/support/migrations/0002_support_role.py`
- Modify: `backend/backoffice/urls.py`
- Modify: `backend/backoffice/views.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_support_management_api.py`
- Test: `backend/tests/test_support_notifications.py`

**Interfaces:**
- Consumes: support models and services, `backoffice.ManagementAuditEvent`, existing notification policy.
- Produces management list, detail, patch, reply, attachment, and summary endpoints.
- Produces Celery task `support.tasks.send_support_notification(case_id, event)`.

- [ ] **Step 1: Write failing role and inbox tests**

```python
def test_attention_role_can_filter_reply_and_assign(attention_client, support_case):
    listed = attention_client.get("/api/v1/management/support/cases/?pending=1")
    assert listed.status_code == 200
    assert listed.json()["results"][0]["case_number"] == support_case.case_number
    replied = attention_client.post(f"/api/v1/management/support/cases/{support_case.public_id}/messages/", {"body": "Te ayudamos", "idempotency_key": "reply-1"}, format="multipart")
    assert replied.status_code == 201


def test_management_audit_never_contains_message_body(owner_client, support_case):
    owner_client.post(f"/api/v1/management/support/cases/{support_case.public_id}/messages/", {"body": "Contenido privado", "idempotency_key": "reply-2"}, format="multipart")
    event = ManagementAuditEvent.objects.latest("created_at")
    assert "Contenido privado" not in str(event.metadata)
```

- [ ] **Step 2: Write failing notification policy tests**

```python
def test_missing_smtp_does_not_block_case_creation(settings, support_case):
    settings.EMAIL_HOST = ""
    result = queue_support_notification(support_case, "created")
    assert result == "disabled"
```

- [ ] **Step 3: Run management tests and verify RED**

Run: `cd backend; pytest tests/test_support_management_api.py tests/test_support_notifications.py -q`
Expected: 404 for missing management routes.

- [ ] **Step 4: Implement indexed list queries, role migration, audit, and Celery notifications**

```python
queryset = (
    SupportCase.objects.select_related("customer", "assigned_to")
    .annotate(message_count=Count("messages"))
    .order_by("-updated_at", "-id")
)
```

Add `Atención` with view, reply, assign, and state permissions. Summary returns only counts. Notification tasks exit successfully when transactional email is disabled.

- [ ] **Step 5: Run management, permission, and query tests and commit**

Run: `cd backend; pytest tests/test_support_management_api.py tests/test_support_notifications.py tests/test_staff_permissions.py -q`
Expected: PASS.

```bash
git add backend/support backend/backoffice backend/config/settings.py backend/tests/test_support_management_api.py backend/tests/test_support_notifications.py
git commit -m "feat: add support management inbox API"
```

### Task 5: Public support routes and on-demand forms

**Files:**
- Create: `frontend/lib/support/types.ts`
- Create: `frontend/lib/support/api.ts`
- Create: `frontend/components/support/support-hub.tsx`
- Create: `frontend/components/support/case-create-dialog.tsx`
- Create: `frontend/components/support/case-recovery-dialog.tsx`
- Create: `frontend/app/consultas/page.tsx`
- Create: `frontend/app/reportar-problema/page.tsx`
- Modify: `frontend/components/account/account-dashboard.tsx`
- Modify: `frontend/components/layout/site-footer.tsx`
- Test: `frontend/tests/support-hub.test.tsx`

**Interfaces:**
- Consumes public API from Task 3.
- Produces `SupportCaseSummary`, `SupportCaseDetail`, `SupportConfiguration`, and `CreateSupportCaseInput` TypeScript types.
- Produces `SupportHub({ initialKind?: "consultation" | "problem" })`.

- [ ] **Step 1: Write failing form-visibility and creation tests**

```tsx
test("mantiene el alta cerrada hasta solicitar una consulta", async () => {
  render(<SupportHub />);
  expect(screen.queryByRole("dialog", { name: "Nueva consulta" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Nueva consulta" }));
  expect(screen.getByRole("dialog", { name: "Nueva consulta" })).toBeVisible();
});

test("reportar un problema abre únicamente el formulario específico", async () => {
  render(<SupportHub initialKind="problem" />);
  expect(screen.getByRole("heading", { name: "Reportar un problema" })).toBeVisible();
  expect(screen.getByLabelText("Categoría")).toBeVisible();
});
```

- [ ] **Step 2: Run Vitest and verify RED**

Run: `cd frontend; npm test -- --run tests/support-hub.test.tsx`
Expected: FAIL because support components and routes do not exist.

- [ ] **Step 3: Implement typed requests and on-demand dialogs**

```tsx
export function SupportHub({ initialKind }: { initialKind?: SupportCaseKind }) {
  const [mode, setMode] = useState<"idle" | "create" | "recover">(initialKind ? "create" : "idle");
  return <main className="support-hub">{/* list, explicit actions, conditional dialogs */}</main>;
}
```

Use `FormData` and generated idempotency keys. Show the recovery code once in a confirmation panel with a copy action.

- [ ] **Step 4: Run tests and commit**

Run: `cd frontend; npm test -- --run tests/support-hub.test.tsx`
Expected: PASS.

```bash
git add frontend/app/consultas frontend/app/reportar-problema frontend/components/support frontend/lib/support frontend/components/account/account-dashboard.tsx frontend/components/layout/site-footer.tsx frontend/tests/support-hub.test.tsx
git commit -m "feat: add public support entry flows"
```

### Task 6: Conversation thread and clipboard attachments

**Files:**
- Create: `frontend/components/support/support-thread.tsx`
- Create: `frontend/components/support/message-composer.tsx`
- Create: `frontend/components/support/attachment-queue.tsx`
- Create: `frontend/components/support/support-attachment.tsx`
- Create: `frontend/app/consultas/[publicId]/page.tsx`
- Modify: `frontend/lib/support/api.ts`
- Test: `frontend/tests/support-thread.test.tsx`
- Test: `frontend/tests/support-clipboard.test.tsx`

**Interfaces:**
- Consumes Task 5 types and Task 3 message/download endpoints.
- Produces `MessageComposer({ disabled, onSend })` where `onSend(body: string, files: File[], idempotencyKey: string): Promise<void>`.
- Produces `filesFromClipboard(event: ClipboardEvent): File[]` and `mergeAttachmentQueue(current, incoming): AttachmentQueueResult`.

- [ ] **Step 1: Write failing clipboard and limit tests**

```tsx
test("pega texto y agrega la imagen del portapapeles", async () => {
  render(<MessageComposer disabled={false} onSend={vi.fn()} />);
  const image = new File(["png"], "captura.png", { type: "image/png" });
  fireEvent.paste(screen.getByLabelText("Mensaje"), clipboardWith("Detalle", image));
  expect(screen.getByLabelText("Mensaje")).toHaveValue("Detalle");
  expect(screen.getByText("captura.png")).toBeVisible();
});

test("rechaza el sexto adjunto antes de enviar", () => {
  const result = mergeAttachmentQueue(fiveFiles, [sixthFile]);
  expect(result.error).toBe("Podés adjuntar hasta 5 archivos por mensaje.");
});
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd frontend; npm test -- --run tests/support-thread.test.tsx tests/support-clipboard.test.tsx`
Expected: FAIL because composer and queue helpers are missing.

- [ ] **Step 3: Implement paste, drag, selection, previews, sending, and closed state**

```tsx
const onPaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
  const files = Array.from(event.clipboardData.items)
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
  if (files.length) addFiles(files);
};
```

Do not prevent the default paste, so text and the browser's native right-click Paste keep working. Revoke object preview URLs on removal and unmount.

- [ ] **Step 4: Run tests and commit**

Run: `cd frontend; npm test -- --run tests/support-thread.test.tsx tests/support-clipboard.test.tsx`
Expected: PASS.

```bash
git add frontend/app/consultas frontend/components/support frontend/lib/support frontend/tests/support-thread.test.tsx frontend/tests/support-clipboard.test.tsx
git commit -m "feat: add support conversation and attachments"
```

### Task 7: Management inbox and case operations

**Files:**
- Create: `frontend/lib/management/support-types.ts`
- Create: `frontend/components/management/support-inbox.tsx`
- Create: `frontend/components/management/support-case-panel.tsx`
- Create: `frontend/app/gestion/consultas/page.tsx`
- Create: `frontend/app/gestion/consultas/[publicId]/page.tsx`
- Modify: `frontend/components/management/management-nav.tsx`
- Modify: `frontend/lib/management/server-api.ts`
- Modify: `frontend/lib/management/api.ts`
- Test: `frontend/tests/management-support.test.tsx`

**Interfaces:**
- Consumes Task 4 management endpoints and Task 6 composer.
- Produces management inbox filters in `searchParams` and compact case detail operations.

- [ ] **Step 1: Write failing inbox and no-reload tests**

```tsx
test("muestra una bandeja compacta y no un formulario de alta", async () => {
  render(await ManagementSupportPage({ searchParams: Promise.resolve({ pending: "1" }) }));
  expect(screen.getByRole("table", { name: "Consultas y problemas" })).toBeVisible();
  expect(screen.queryByLabelText("Asunto de nueva consulta")).not.toBeInTheDocument();
});

test("responde y actualiza el hilo sin recargar la página", async () => {
  render(<ManagementSupportCasePanel initialCase={caseDetail} />);
  await user.type(screen.getByLabelText("Mensaje"), "Respuesta del equipo");
  await user.click(screen.getByRole("button", { name: "Enviar respuesta" }));
  expect(await screen.findByText("Respuesta del equipo")).toBeVisible();
});
```

- [ ] **Step 2: Run test and verify RED**

Run: `cd frontend; npm test -- --run tests/management-support.test.tsx`
Expected: FAIL because the management support routes do not exist.

- [ ] **Step 3: Implement list, URL filters, detail, assignment, state, priority, and nav count**

```tsx
const sections = [
  ["Inicio", "/gestion"],
  ["Catálogo", "/gestion/catalogo"],
  ["Inventario", "/gestion/inventario"],
  ["Pedidos", "/gestion/pedidos"],
  ["Clientes", "/gestion/clientes"],
  ["Consultas", "/gestion/consultas"],
  ["Contenido", "/gestion/contenido"],
  ["Promociones", "/gestion/promociones"],
  ["Envíos", "/gestion/envios"],
  ["Integraciones", "/gestion/integraciones"],
  ["Usuarios", "/gestion/usuarios"],
  ["Auditoría", "/gestion/auditoria"],
  ["Configuración", "/gestion/configuracion"],
] as const;
```

Render the count as an accessible badge with text in the link's accessible name. Use PATCH with optimistic disabled state, then replace data from the server response.

- [ ] **Step 4: Run test and commit**

Run: `cd frontend; npm test -- --run tests/management-support.test.tsx tests/management-foundation.test.tsx`
Expected: PASS.

```bash
git add frontend/app/gestion/consultas frontend/components/management frontend/lib/management frontend/tests/management-support.test.tsx
git commit -m "feat: add support management inbox"
```

### Task 8: Theme, responsive behavior, accessibility, and full verification

**Files:**
- Modify: `frontend/app/styles.css`
- Modify: `frontend/tests/mock-api.mjs`
- Create: `frontend/tests/e2e/support.spec.ts`
- Modify: `frontend/tests/e2e/accessibility.spec.ts`
- Modify: `backend/tests/test_openapi_semantics.py`

**Interfaces:**
- Consumes all prior tasks.
- Produces complete theme-aware support UI and end-to-end coverage.

- [ ] **Step 1: Write failing theme and responsive assertions**

```tsx
test("support usa únicamente los roles del tema", () => {
  const css = readFileSync("app/styles.css", "utf8");
  const supportCss = css.slice(css.indexOf("/* Support conversations */"));
  expect(supportCss).toContain("var(--magenta-action)");
  expect(supportCss).toContain("var(--surface-cold)");
  expect(supportCss).not.toMatch(/#[0-9a-f]{3,8}/i);
});
```

Add Playwright assertions that `/consultas`, a thread, `/reportar-problema`, the inbox, and management detail have no horizontal overflow at 360 and 1440 px.

- [ ] **Step 2: Run targeted suites and verify RED**

Run: `cd frontend; npm test -- --run tests/support-hub.test.tsx tests/support-thread.test.tsx tests/management-support.test.tsx`
Expected: FAIL until the support styles and mock contracts exist.

- [ ] **Step 3: Implement Impeccable Operate styling and states**

```css
/* Support conversations */
.support-shell { color: var(--ink); }
.support-case-row { border: 1px solid var(--line); background: var(--surface-elevated); }
.support-primary-action { background: var(--magenta-action); color: var(--surface); }
.support-composer:focus-within { border-color: var(--cyan-action); }
```

Cover 360/768/1024/1440 layouts, keyboard focus, `aria-live`, empty/loading/error/offline/closed states, and `prefers-reduced-motion`.

- [ ] **Step 4: Run backend and frontend verification**

Run: `cd backend; pytest tests/test_support_domain.py tests/test_support_services.py tests/test_support_attachments.py tests/test_support_api.py tests/test_support_management_api.py tests/test_support_notifications.py tests/test_openapi_semantics.py -q`
Expected: PASS.

Run: `cd frontend; npm run test:ci && npm run lint && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 5: Run E2E, Impeccable detector, and visual review**

Run: `cd frontend; npm run test:e2e -- tests/e2e/support.spec.ts tests/e2e/accessibility.spec.ts`
Expected: PASS.

Run once after UI is complete:

```bash
node C:\Users\edespinoza\.codex\skills\impeccable\scripts\detect.mjs --json frontend/app/consultas frontend/app/reportar-problema frontend/app/gestion/consultas frontend/components/support frontend/components/management frontend/app/styles.css
```

Capture desktop and mobile into `.impeccable/review/`, apply one batched correction, and obtain the Impeccable finish-reviewer disposition before completion.

- [ ] **Step 6: Commit the verified feature**

```bash
git add backend frontend docs/superpowers/plans/2026-08-23-support-conversations.md
git commit -m "feat: complete support conversations module"
```
