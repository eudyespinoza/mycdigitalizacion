import csv
import io
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from PIL import Image

from tests.test_commerce_domain import make_variant
from tests.test_commerce_round1 import pending_order


def image_upload(name="hero.png", *, size=(32, 24), image_format="PNG", content_type="image/png"):
    output = io.BytesIO()
    Image.new("RGB", size, "#335577").save(output, format=image_format)
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


@pytest.mark.django_db
def test_role_setup_command_is_idempotent_and_least_privilege():
    from config.admin_roles import sync_admin_roles

    first = sync_admin_roles()
    second = sync_admin_roles()
    call_command("setup_admin_roles")

    assert first == second == {
        "Owner": first["Owner"],
        "Catalog": first["Catalog"],
        "Orders/Logistics": first["Orders/Logistics"],
        "Content": first["Content"],
    }
    assert Group.objects.filter(
        name__in=("Owner", "Catalog", "Orders/Logistics", "Content")
    ).count() == 4
    catalog = Group.objects.get(name="Catalog")
    owner = Group.objects.get(name="Owner")
    logistics = Group.objects.get(name="Orders/Logistics")
    content = Group.objects.get(name="Content")
    assert catalog.permissions.filter(codename="change_product").exists()
    assert catalog.permissions.filter(codename="import_product").exists()
    assert not catalog.permissions.filter(codename="view_order").exists()
    assert logistics.permissions.filter(codename="view_order").exists()
    assert logistics.permissions.filter(codename="cancel_order").exists()
    assert not logistics.permissions.filter(codename="change_order").exists()
    assert content.permissions.filter(codename="change_heroslide").exists()
    assert not content.permissions.filter(codename="change_product").exists()
    assert owner.permissions.filter(
        content_type__app_label="auth", codename="change_group"
    ).exists()
    assert not owner.permissions.filter(
        content_type__app_label="admin", codename="delete_logentry"
    ).exists()


@pytest.mark.django_db
@override_settings(ADMIN_LOGIN_MAX_ATTEMPTS=3, ADMIN_LOGIN_LOCK_SECONDS=60)
def test_admin_login_rate_limit_blocks_correct_password_after_failed_window(django_user_model, rf):
    from config.admin_security import RateLimitedAdminAuthenticationForm

    cache.clear()
    user = django_user_model.objects.create_superuser(
        email="owner@example.test", password="Correct-Horse-Battery-Staple-42"
    )
    request = rf.post("/admin/login/", REMOTE_ADDR="203.0.113.8")
    for _ in range(3):
        form = RateLimitedAdminAuthenticationForm(
            request,
            data={"username": user.email, "password": "incorrect"},
        )
        assert not form.is_valid()

    blocked = RateLimitedAdminAuthenticationForm(
        request,
        data={"username": user.email, "password": "Correct-Horse-Battery-Staple-42"},
    )
    assert not blocked.is_valid()
    assert "Demasiados intentos" in str(blocked.non_field_errors())


@pytest.mark.django_db
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
def test_admin_branding_and_accessible_assets_render(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        email="brand-owner@example.test", password="Correct-Horse-Battery-Staple-42"
    )
    client.force_login(user)
    response = client.get("/admin/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "mycdigitalizacion" in body
    assert "mycdigitalizacion-mark.svg" in body
    assert "mycdigitalizacion.css" in body
    assert "Atajos operativos" in body


@pytest.mark.django_db
@override_settings(ADMIN_2FA_REQUIRED=True, ADMIN_2FA_VERIFICATION_URL="/admin/2fa/")
def test_admin_two_factor_gate_is_opt_in_and_session_ready(django_user_model, rf):
    from config.admin_security import AdminTwoFactorGateMiddleware

    user = django_user_model.objects.create_user(email="staff-2fa@example.test", is_staff=True)
    request = rf.get("/admin/")
    request.user = user
    request.session = {}
    middleware = AdminTwoFactorGateMiddleware(lambda _: "allowed")

    blocked = middleware(request)
    assert blocked.status_code == 302
    assert blocked.url == "/admin/2fa/?next=%2Fadmin%2F"
    request.session["admin_2fa_verified"] = True
    assert middleware(request) == "allowed"


@pytest.mark.django_db
def test_cms_requires_alt_only_with_image_and_validates_presentation_controls():
    from landing.models import HeroSlide, PromotionPopup

    HeroSlide(title="Texto sin imagen", alt_text="").full_clean()
    with pytest.raises(ValidationError, match="alt"):
        HeroSlide(
            title="Imagen sin alt", alt_text="", desktop_image=image_upload()
        ).full_clean()
    with pytest.raises(ValidationError):
        HeroSlide(title="Intervalo", alt_text="", interval_ms=500).full_clean()
    with pytest.raises(ValidationError):
        PromotionPopup(
            title="Frecuencia",
            alt_text="",
            frequency="sometimes",
            display_delay_ms=70_000,
        ).full_clean()


@pytest.mark.django_db
def test_cms_api_exposes_motion_interval_and_popup_frequency(client):
    from landing.models import HeroSlide, PromotionPopup, PromotionSlide

    HeroSlide.objects.create(
        title="Hero", alt_text="", interval_ms=7000, pause_on_reduced_motion=True
    )
    PromotionSlide.objects.create(
        title="Promo", alt_text="", interval_ms=9000, pause_on_reduced_motion=False
    )
    PromotionPopup.objects.create(
        title="Popup",
        alt_text="",
        frequency="daily",
        display_delay_ms=2500,
        dismissible=False,
    )

    settings = client.get("/api/v1/storefront/home/").json()
    assert settings["hero_slides"][0]["interval_ms"] == 7000
    assert settings["hero_slides"][0]["pause_on_reduced_motion"] is True
    assert settings["promotion_slides"][0]["interval_ms"] == 9000
    assert settings["promotion_slides"][0]["pause_on_reduced_motion"] is False
    assert settings["promotion_popups"][0]["frequency"] == "daily"
    assert settings["promotion_popups"][0]["display_delay_ms"] == 2500
    assert settings["promotion_popups"][0]["dismissible"] is False


@pytest.mark.django_db
def test_cms_admin_duplicates_content_and_renders_safe_thumbnail(rf):
    from landing.admin import ScheduledContentAdmin
    from landing.models import HeroSlide

    slide = HeroSlide.objects.create(
        title="Original",
        alt_text="Vista previa",
        desktop_image="landing/desktop/original.png",
        order=3,
    )
    model_admin = ScheduledContentAdmin(HeroSlide, AdminSite())
    request = rf.post("/admin/landing/heroslide/")
    request.user = type("Staff", (), {"has_perm": lambda *_: True})()
    model_admin.duplicate_selected(request, HeroSlide.objects.filter(pk=slide.pk))

    duplicate = HeroSlide.objects.exclude(pk=slide.pk).get()
    assert duplicate.title == "Original (copia)"
    assert duplicate.order == 4
    assert "<img" in str(model_admin.thumbnail(slide))
    assert "Vista previa" in str(model_admin.thumbnail(slide))
    assert model_admin.list_editable == ("order",)
    assert "admin/js/mycd-sortable.js" in model_admin.media._js


@pytest.mark.django_db
def test_catalog_variant_admin_embeds_typed_attributes_and_inventory_history():
    from catalog.admin import AttributeValueInline, ProductVariantAdmin
    from catalog.models import ProductVariant

    model_admin = ProductVariantAdmin(ProductVariant, AdminSite())

    assert AttributeValueInline in model_admin.inlines
    assert "inventory_history" in model_admin.list_display


@pytest.mark.django_db
@override_settings(
    MAX_IMAGE_UPLOAD_BYTES=1024 * 1024,
    MAX_IMAGE_WIDTH=100,
    MAX_IMAGE_HEIGHT=100,
    MAX_IMAGE_PIXELS=10_000,
)
def test_media_validation_rejects_spoofed_mime_dimensions_and_unsafe_name(tmp_path):
    from config.media import safe_image_upload_to, validate_image_upload

    spoofed = image_upload(content_type="application/pdf")
    with pytest.raises(ValidationError, match="MIME"):
        validate_image_upload(spoofed)
    oversized_dimensions = image_upload(size=(101, 20))
    with pytest.raises(ValidationError, match="dimensions"):
        validate_image_upload(oversized_dimensions)
    safe_path = safe_image_upload_to("landing/desktop")(
        None, "../../=SUM(A1:A2) evil name.PNG"
    )
    assert safe_path.startswith("landing/desktop/")
    assert safe_path.endswith(".png")
    assert ".." not in safe_path
    assert "SUM" not in safe_path


@pytest.mark.django_db
def test_media_derivatives_keep_original_and_degrade_without_avif(tmp_path):
    from django.core.files.storage import FileSystemStorage

    from config.media import generate_image_derivatives

    storage = FileSystemStorage(location=tmp_path, base_url="/media/")
    original_name = storage.save("original/photo.png", image_upload())
    with override_settings(MEDIA_DERIVATIVE_FORMATS=("AVIF", "WEBP")):
        derivatives = generate_image_derivatives(
            storage=storage,
            name=original_name,
            supported_formats={"WEBP"},
        )

    assert storage.exists(original_name)
    assert set(derivatives) == {"webp", "fallback"}
    assert all(storage.exists(name) for name in derivatives.values())


@pytest.mark.django_db
def test_product_csv_dry_run_validates_all_rows_and_writes_only_when_committed(
    django_user_model,
):
    from catalog.admin_io import import_products_csv
    from catalog.models import Category, ProductVariant

    actor = django_user_model.objects.create_user(email="catalog@example.test", is_staff=True)
    Category.objects.create(name="Papeles", slug="papeles")
    valid_csv = SimpleUploadedFile(
        "products.csv",
        (
            b"sku,product_name,product_slug,category_slug,variant_name,price,cost,on_hand,"
            b"weight_grams,length_cm,width_cm,height_cm\n"
            b"SKU-CSV,Papel A4,papel-a4,papeles,Resma,1250.50,900.25,12,500,30,21,5\n"
        ),
        content_type="text/csv",
    )
    dry = import_products_csv(valid_csv, dry_run=True, actor=actor)
    assert dry.valid_rows == 1
    assert dry.errors == ()
    assert not ProductVariant.objects.filter(sku="SKU-CSV").exists()

    valid_csv.seek(0)
    committed = import_products_csv(valid_csv, dry_run=False, actor=actor)
    assert committed.created_variants == 1
    assert ProductVariant.objects.get(sku="SKU-CSV").cost == Decimal("900.25")

    invalid_csv = SimpleUploadedFile(
        "invalid.csv",
        (
            b"sku,product_name,product_slug,category_slug,variant_name,price,cost,on_hand,"
            b"weight_grams,length_cm,width_cm,height_cm\n"
            b"BAD-1,Papel,papel-bad,missing,,oops,10,1,1,1,1,1\n"
            b"BAD-2,Papel,papel-bad,papeles,,10,-1,1,1,1,1,1\n"
        ),
    )
    invalid = import_products_csv(invalid_csv, dry_run=False, actor=actor)
    assert {error.row for error in invalid.errors} == {2, 3}
    assert not ProductVariant.objects.filter(sku__startswith="BAD-").exists()


@pytest.mark.django_db
def test_product_export_neutralizes_formula_cells_and_keeps_cost_admin_only(client):
    from catalog.admin_io import export_products_csv

    variant = make_variant(sku="CSV-FORMULA")
    variant.product.name = "=HYPERLINK(\"https://evil.test\")"
    variant.product.save(update_fields=("name",))

    rows = list(csv.DictReader(io.StringIO(export_products_csv([variant]).decode())))
    assert rows[0]["product_name"].startswith("'=")
    assert rows[0]["cost"] == str(variant.cost)
    public = client.get(f"/api/v1/products/{variant.product.slug}/").json()
    assert "cost" not in public["variants"][0]


@pytest.mark.django_db
def test_guarded_order_action_requires_exact_permission_and_audits(django_user_model):
    from commerce.admin_services import perform_order_admin_action
    from commerce.models import Cart, CartLine

    customer = django_user_model.objects.create_user(email="buyer-admin@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="ADMIN-CANCEL"), quantity=1)
    order = pending_order(cart)
    staff = django_user_model.objects.create_user(email="operator@example.test", is_staff=True)

    with pytest.raises(PermissionDenied):
        perform_order_admin_action(
            action="cancel", order=order, actor=staff, reason="Pedido duplicado"
        )
    permission = Permission.objects.get(codename="cancel_order")
    staff.user_permissions.add(permission)
    staff = django_user_model.objects.get(pk=staff.pk)
    result = perform_order_admin_action(
        action="cancel", order=order, actor=staff, reason="Pedido duplicado"
    )

    assert result.fulfillment_status == "cancelled"
    event = order.audit_events.get(kind="admin_cancelled")
    assert event.actor == staff
    assert event.data == {"reason": "Pedido duplicado"}


@pytest.mark.django_db
def test_order_admin_exposes_only_guarded_sensitive_actions():
    from commerce.admin import OrderAdmin
    from commerce.models import Order

    model_admin = OrderAdmin(Order, AdminSite())
    assert set(model_admin.actions) == {
        "approve_identity_selected",
        "resume_selected",
        "cancel_selected",
        "refund_selected",
        "create_shipment_selected",
        "refresh_tracking_selected",
        "export_selected_csv",
        "export_selected_xlsx",
    }
    assert model_admin.has_change_permission(RequestFactory().get("/admin/")) is False


@pytest.mark.django_db
def test_order_admin_action_visibility_uses_specific_permission(django_user_model):
    from commerce.admin import OrderAdmin
    from commerce.models import Order

    operator = django_user_model.objects.create_user(email="logistics@example.test", is_staff=True)
    operator.user_permissions.add(
        Permission.objects.get(codename="view_order"),
        Permission.objects.get(codename="cancel_order"),
    )
    operator = django_user_model.objects.get(pk=operator.pk)
    request = RequestFactory().get("/admin/commerce/order/")
    request.user = operator

    actions = OrderAdmin(Order, AdminSite()).get_actions(request)

    assert "cancel_selected" in actions
    assert "refund_selected" not in actions
    assert "export_selected_csv" not in actions


@pytest.mark.django_db
def test_readyz_reports_bounded_dependency_state_without_diagnostics(client, monkeypatch):
    import config.views

    monkeypatch.setattr(config.views, "redis_is_ready", lambda: True)
    ready = client.get("/readyz")
    monkeypatch.setattr(config.views, "redis_is_ready", lambda: False)
    unavailable = client.get("/readyz")

    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "dependencies": {"database": "ok", "redis": "ok"},
    }
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "status": "not_ready",
        "dependencies": {"database": "ok", "redis": "unavailable"},
    }


@pytest.mark.django_db
def test_fiscal_csv_and_xlsx_mask_by_permission_neutralize_formulas_and_audit(
    django_user_model,
):
    from openpyxl import load_workbook

    from accounts.models import BillingProfile, CustomerProfile
    from commerce.exports import export_billing_profiles
    from commerce.models import StaffExportAudit

    customer_user = django_user_model.objects.create_user(email="fiscal@example.test")
    customer = CustomerProfile.objects.create(user=customer_user, consent_version="privacy-v1")
    billing = BillingProfile(
        customer=customer,
        label="=SUM(A1:A2)",
        legal_name="+Empresa",
        tax_condition="Responsable inscripto",
    )
    billing.set_cuit("20123456786")
    billing.save()
    operator = django_user_model.objects.create_user(email="exporter@example.test", is_staff=True)

    masked = export_billing_profiles(
        BillingProfile.objects.all(),
        actor=operator,
        export_format="csv",
        filters={"tax_condition": "Responsable inscripto"},
    )
    masked_row = next(csv.DictReader(io.StringIO(masked.decode("utf-8-sig"))))
    assert masked_row["cuit"] == "••-••••••••-6"
    assert masked_row["label"].startswith("'=")
    assert masked_row["legal_name"].startswith("'+")

    operator.user_permissions.add(Permission.objects.get(codename="view_sensitive_fiscal_data"))
    operator = django_user_model.objects.get(pk=operator.pk)
    xlsx = export_billing_profiles(
        BillingProfile.objects.all(), actor=operator, export_format="xlsx", filters={}
    )
    sheet = load_workbook(io.BytesIO(xlsx), read_only=True).active
    values = list(sheet.values)
    assert values[1][3] == "20123456786"
    assert values[1][0].startswith("'=")
    assert StaffExportAudit.objects.filter(actor=operator).count() == 2
    audit = StaffExportAudit.objects.filter(actor=operator).latest("created_at")
    assert audit.resource == "billing_profiles"
    assert audit.row_count == 1
    assert audit.filters == {}
    assert not hasattr(audit, "payload")
