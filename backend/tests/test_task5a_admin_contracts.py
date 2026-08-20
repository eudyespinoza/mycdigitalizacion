import csv
import io
import json
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache, caches
from django.core.cache.backends.locmem import LocMemCache
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


class PassingAdminTwoFactorProvider:
    def begin(self, request, callback_url):
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(f"{callback_url}?proof=accepted")

    def verify(self, request):
        return request.GET.get("proof") == "accepted"


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
    caches["admin_login"].clear()
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


def test_admin_throttle_is_atomic_across_independent_shared_cache_clients():
    from config.admin_security import AdminLoginThrottle

    first_worker = AdminLoginThrottle(LocMemCache("admin-shared", {}), maximum=3, timeout=60)
    second_worker = AdminLoginThrottle(LocMemCache("admin-shared", {}), maximum=3, timeout=60)

    assert first_worker.reserve("same-key") == 1
    assert second_worker.reserve("same-key") == 2
    assert first_worker.reserve("same-key") == 3
    assert second_worker.reserve("same-key") == 4
    assert second_worker.is_blocked("same-key") is True


def test_admin_cache_uses_redis_in_production_and_explicit_dev_fallback():
    from config.settings import admin_cache_config

    assert admin_cache_config({"APP_ENV": "production", "REDIS_URL": "redis://redis:6379/0"}) == {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/0",
        "KEY_PREFIX": "mycd-admin",
    }
    assert admin_cache_config({"APP_ENV": "development"})["BACKEND"].endswith(
        "LocMemCache"
    )


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
@override_settings(
    ADMIN_2FA_REQUIRED=True,
    ADMIN_2FA_PROVIDER="tests.test_task5a_admin_contracts.PassingAdminTwoFactorProvider",
)
def test_admin_two_factor_provider_completes_and_logout_clears_session(
    client, django_user_model
):
    user = django_user_model.objects.create_superuser(
        email="staff-2fa@example.test", password="Correct-Horse-Battery-Staple-42"
    )

    login = client.post(
        "/admin/login/?next=/admin/",
        {"username": user.email, "password": "Correct-Horse-Battery-Staple-42"},
    )
    challenge = client.get(login.url)
    provider_redirect = client.get(challenge.url)
    verified = client.get(provider_redirect.url)

    assert login.status_code == 302 and login.url == "/admin/"
    assert challenge.status_code == 302 and challenge.url.startswith("/admin/2fa/")
    assert provider_redirect.status_code == 302
    assert verified.status_code == 302 and verified.url == "/admin/"
    assert client.get("/admin/").status_code == 200
    client.post("/admin/logout/")
    assert "admin_2fa_verified" not in client.session


def test_admin_two_factor_required_without_provider_fails_fast():
    from django.core.exceptions import ImproperlyConfigured

    from config.admin_security import validate_admin_two_factor_settings

    with pytest.raises(ImproperlyConfigured, match="ADMIN_2FA_PROVIDER"):
        validate_admin_two_factor_settings(required=True, provider_path="")


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


def test_openapi_documents_responsive_media_source_contract(client):
    schema = client.get("/api/v1/schema/?format=json").json()
    components = schema["components"]["schemas"]
    hero_sources = components["HeroSlide"]["properties"]["desktop_responsive_sources"]
    media_sources = components["ProductMedia"]["properties"]["responsive_sources"]

    for sources in (hero_sources, media_sources):
        assert sources["type"] == "array"
        item = components[sources["items"]["$ref"].rsplit("/", 1)[-1]]
        assert item["required"] == ["fallback", "width"]
        assert item["properties"]["width"]["type"] == "integer"
        assert item["properties"]["fallback"]["type"] == "string"


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
    assert model_admin.list_editable == ()
    assert "admin/js/mycd-sortable.js" in model_admin.media._js


@pytest.mark.django_db
def test_cms_reorder_endpoint_preserves_global_order_across_page_boundaries(
    client, django_user_model
):
    from landing.models import HeroSlide

    editor = django_user_model.objects.create_superuser(email="reorder@example.test")
    client.force_login(editor)
    slides = [HeroSlide.objects.create(title=f"Slide {index}", order=index) for index in range(205)]

    response = client.post(
        "/admin/landing/heroslide/reorder/",
        data=json.dumps(
            {"item_id": slides[150].pk, "target_id": slides[99].pk, "position": "before"}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    ordered_ids = list(HeroSlide.objects.order_by("order", "pk").values_list("pk", flat=True))
    assert ordered_ids[99:102] == [slides[150].pk, slides[99].pk, slides[100].pk]
    assert list(HeroSlide.objects.order_by("order").values_list("order", flat=True)) == list(
        range(205)
    )
    retry = client.post(
        "/admin/landing/heroslide/reorder/",
        data=json.dumps(
            {"item_id": slides[150].pk, "target_id": slides[99].pk, "position": "before"}
        ),
        content_type="application/json",
    )
    assert retry.status_code == 200
    assert list(
        HeroSlide.objects.order_by("order", "pk").values_list("pk", flat=True)
    ) == ordered_ids


@pytest.mark.django_db
def test_cms_preview_is_record_specific_protected_and_includes_draft_controls(
    client, django_user_model
):
    from django.utils import timezone

    from landing.models import HeroSlide

    slide = HeroSlide.objects.create(
        title="Borrador futuro",
        body="Contenido privado",
        enabled=False,
        starts_at=timezone.now() + timezone.timedelta(days=3),
        desktop_image="landing/desktop/draft.jpg",
        mobile_image="landing/mobile/draft.jpg",
        alt_text="Vista del borrador",
        focal_x=Decimal("31.50"),
        focal_y=Decimal("62.00"),
        safe_height_mobile=280,
        safe_height_tablet=410,
        safe_height_desktop=560,
    )
    url = f"/admin/landing/heroslide/{slide.pk}/preview/"

    assert client.get(url).status_code == 302
    viewer = django_user_model.objects.create_superuser(email="preview@example.test")
    client.force_login(viewer)
    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    for literal in (
        "Borrador futuro",
        "Contenido privado",
        "/media/landing/desktop/draft.jpg",
        "/media/landing/mobile/draft.jpg",
        "31.50% 62.00%",
        "280px",
        "410px",
        "560px",
    ):
        assert literal in body


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
    from config.media import validate_image_upload

    spoofed = image_upload(content_type="application/pdf")
    with pytest.raises(ValidationError, match="MIME"):
        validate_image_upload(spoofed)
    oversized_dimensions = image_upload(size=(101, 20))
    with pytest.raises(ValidationError, match="dimensions"):
        validate_image_upload(oversized_dimensions)
    unsafe_name = image_upload("../../=SUM(A1:A2) evil name.PNG")
    validate_image_upload(unsafe_name)
    assert unsafe_name._detected_extension == ".png"


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
    assert [source["width"] for source in derivatives["widths"]] == [32]
    assert set(derivatives["widths"][0]) == {"width", "webp", "fallback"}
    assert all(
        storage.exists(name)
        for source in derivatives["widths"]
        for key, name in source.items()
        if key != "width"
    )


@pytest.mark.django_db
def test_product_media_derives_extension_from_content_and_serializes_responsive_sources(
    tmp_path,
):
    from django.core.files.storage import FileSystemStorage

    from catalog.models import ProductMedia
    from catalog.serializers import ProductMediaSerializer

    variant = make_variant(sku="MEDIA-LIFECYCLE")
    with override_settings(
        MEDIA_ROOT=tmp_path,
        STORAGES={
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(tmp_path), "base_url": "/media/"},
            },
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        },
        MEDIA_RESPONSIVE_WIDTHS=(320, 640),
    ):
        media = ProductMedia.objects.create(
            product=variant.product,
            file=image_upload("wrong.JPG", size=(800, 450), content_type="image/png"),
            alt_text="Producto responsive",
        )
        assert media.file.name.endswith(".png")
        assert [source["width"] for source in media.derivatives["widths"]] == [320, 640]
        payload = ProductMediaSerializer(media).data
        assert payload["responsive_sources"][0]["width"] == 320
        assert payload["responsive_sources"][0]["fallback"].startswith("/media/")
        assert "cost" not in payload
        assert isinstance(media.file.storage, FileSystemStorage)


@pytest.mark.django_db
def test_landing_image_replacement_regenerates_and_removal_cleans_superseded_assets(tmp_path):
    from landing.models import HeroSlide
    from landing.serializers import HeroSlideSerializer

    storage_settings = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path), "base_url": "/media/"},
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    with override_settings(
        MEDIA_ROOT=tmp_path,
        STORAGES=storage_settings,
        MEDIA_RESPONSIVE_WIDTHS=(80, 160, 320),
    ):
        slide = HeroSlide.objects.create(
            title="Lifecycle",
            alt_text="Imagen",
            desktop_image=image_upload(size=(320, 180)),
        )
        original_source = slide.desktop_image.name
        old_paths = [
            path
            for source in slide.desktop_derivatives["widths"]
            for key, path in source.items()
            if key != "width"
        ]
        slide.desktop_image = image_upload("replacement", size=(160, 90))
        slide.save()
        assert slide.desktop_image.name.endswith(".png")
        assert [source["width"] for source in slide.desktop_derivatives["widths"]] == [80, 160]
        assert not slide.desktop_image.storage.exists(original_source)
        assert all(not slide.desktop_image.storage.exists(path) for path in old_paths)
        assert HeroSlideSerializer(slide).data["desktop_responsive_sources"][1]["width"] == 160

        current_source = slide.desktop_image.name
        slide.desktop_image = None
        slide.alt_text = ""
        slide.save()
        assert slide.desktop_derivatives == {}
        assert not slide.desktop_image.storage.exists(current_source)


@pytest.mark.django_db
def test_product_csv_dry_run_validates_all_rows_and_writes_only_when_committed(
    django_user_model,
):
    from catalog.admin_io import import_products_csv
    from catalog.models import Category, ProductVariant
    from commerce.models import InventoryMovement

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
    movement = InventoryMovement.objects.get(variant__sku="SKU-CSV")
    assert movement.quantity_delta == 12
    assert movement.actor == actor
    assert movement.source == "catalog_csv"

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
def test_product_csv_returns_bounded_file_errors_for_encoding_headers_rows_and_slug_conflicts(
    django_user_model,
):
    from catalog.admin_io import validate_product_csv
    from catalog.models import Category, Product

    category = Category.objects.create(name="Papeles CSV", slug="papeles-csv")
    Product.objects.create(name="Existente", slug="existente", category=category)
    broken = validate_product_csv(SimpleUploadedFile("broken.csv", b"\xff\xfe\x00\x00"))
    duplicate_header = validate_product_csv(
        SimpleUploadedFile("headers.csv", b"sku,sku\nA,B\n")
    )
    with override_settings(CATALOG_CSV_MAX_BYTES=8):
        oversized = validate_product_csv(SimpleUploadedFile("large.csv", b"x" * 9))
    conflict_csv = SimpleUploadedFile(
        "conflict.csv",
        (
            b"sku,product_name,product_slug,category_slug,variant_name,price,cost,on_hand,"
            b"weight_grams,length_cm,width_cm,height_cm\n"
            b"CONFLICT,Nombre distinto,existente,papeles-csv,Unidad,10,5,1,1,1,1,1\n"
        ),
    )
    conflict = validate_product_csv(conflict_csv)

    assert broken[1][0].field == "file" and "UTF-8" in broken[1][0].message
    assert duplicate_header[1][0].field == "header"
    assert oversized[1][0].field == "file" and "size" in oversized[1][0].message
    assert conflict[1][0].field == "product_slug"


@pytest.mark.django_db
def test_inventory_adjustment_is_locked_audited_and_admin_stock_is_readonly(django_user_model):
    from catalog.admin import ProductVariantAdmin, ProductVariantInline
    from catalog.models import ProductVariant
    from commerce.inventory import adjust_inventory

    variant = make_variant(sku="STOCK-SERVICE", on_hand=5)
    actor = django_user_model.objects.create_user(email="stock@example.test", is_staff=True)
    adjusted = adjust_inventory(
        variant=variant,
        new_on_hand=9,
        actor=actor,
        source="admin",
        reference="Conteo físico 2026-08-20",
    )

    assert adjusted.on_hand == 9
    movement = adjusted.inventory_movements.get(kind="adjustment")
    assert movement.quantity_delta == 4
    assert movement.actor == actor
    assert movement.source == "admin"
    assert "on_hand" in ProductVariantAdmin(ProductVariant, AdminSite()).readonly_fields
    assert "on_hand" in ProductVariantInline.readonly_fields


@pytest.mark.django_db
def test_inventory_admin_adjustment_route_uses_service_and_actor(client, django_user_model):
    from commerce.models import InventoryMovement

    variant = make_variant(sku="STOCK-ADMIN-ROUTE", on_hand=3)
    owner = django_user_model.objects.create_superuser(email="stock-owner@example.test")
    client.force_login(owner)
    response = client.post(
        f"/admin/catalog/productvariant/{variant.pk}/adjust-stock/",
        {"new_on_hand": "11", "reference": "Recepción proveedor 44"},
    )

    assert response.status_code == 302
    variant.refresh_from_db()
    assert variant.on_hand == 11
    movement = InventoryMovement.objects.get(variant=variant, source="admin")
    assert movement.quantity_delta == 8 and movement.actor == owner


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
@pytest.mark.parametrize(
    ("fulfillment_status", "allowed"),
    (
        ("unfulfilled", True),
        ("preparing", True),
        ("ready_for_pickup", True),
        ("shipped", False),
        ("fulfilled", False),
        ("cancelled", True),
    ),
)
def test_order_cancellation_enforces_locked_state_matrix_and_is_idempotent(
    django_user_model, fulfillment_status, allowed
):
    from commerce.cancellation import OrderCancellationError, cancel_order
    from commerce.models import Cart, CartLine
    from commerce.services import transition_order_status

    customer = django_user_model.objects.create_user(
        email=f"cancel-{fulfillment_status}@example.test"
    )
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(
        cart=cart, variant=make_variant(sku=f"CANCEL-{fulfillment_status}"), quantity=1
    )
    order = pending_order(cart)
    if fulfillment_status != "unfulfilled":
        order = transition_order_status(
            order=order, field="fulfillment_status", value=fulfillment_status
        )
    actor = django_user_model.objects.create_user(
        email=f"operator-{fulfillment_status}@example.test", is_staff=True
    )

    if not allowed:
        with pytest.raises(OrderCancellationError) as error:
            cancel_order(order=order, actor=actor, reason="Solicitud del cliente")
        assert error.value.code == "return_required"
        order.refresh_from_db()
        assert order.fulfillment_status == fulfillment_status
        return

    first = cancel_order(order=order, actor=actor, reason="Solicitud del cliente")
    second = cancel_order(order=order, actor=actor, reason="Solicitud del cliente")
    assert first.fulfillment_status == second.fulfillment_status == "cancelled"
    assert order.audit_events.filter(kind="admin_cancelled").count() == 1


@pytest.mark.django_db
def test_paid_order_cancellation_requires_refund_semantics(django_user_model):
    from commerce.cancellation import OrderCancellationError, cancel_order
    from commerce.models import Cart, CartLine
    from commerce.services import transition_order_status

    customer = django_user_model.objects.create_user(email="paid-cancel@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="PAID-CANCEL"), quantity=1)
    order = pending_order(cart)
    order = transition_order_status(order=order, field="payment_status", value="paid")
    actor = django_user_model.objects.create_user(email="paid-operator@example.test", is_staff=True)

    with pytest.raises(OrderCancellationError) as error:
        cancel_order(order=order, actor=actor, reason="Solicitud del cliente")
    assert error.value.code == "paid_order_requires_refund"


@pytest.mark.django_db
def test_order_admin_exposes_only_guarded_sensitive_actions():
    from commerce.admin import OrderAdmin, ShipmentInline
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
    assert model_admin.has_add_permission(RequestFactory().get("/admin/")) is False
    assert ShipmentInline in model_admin.inlines
    assert set(("status", "tracking_number", "safe_label_link")).issubset(
        ShipmentInline.readonly_fields
    )


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
def test_order_admin_sensitive_action_requires_operator_reason_and_preserves_it(
    client, django_user_model
):
    from commerce.models import Cart, CartLine

    customer = django_user_model.objects.create_user(email="reason-buyer@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="REASON-CANCEL"), quantity=1)
    order = pending_order(cart)
    owner = django_user_model.objects.create_superuser(email="reason-owner@example.test")
    client.force_login(owner)
    url = "/admin/commerce/order/"
    missing = client.post(
        url,
        {"action": "cancel_selected", "_selected_action": str(order.pk), "index": "0"},
    )
    order.refresh_from_db()
    assert missing.status_code == 302 and order.fulfillment_status == "unfulfilled"

    completed = client.post(
        url,
        {
            "action": "cancel_selected",
            "_selected_action": str(order.pk),
            "index": "0",
            "reason": "Cliente solicitó cancelar por duplicado",
        },
    )
    order.refresh_from_db()
    assert completed.status_code == 302 and order.fulfillment_status == "cancelled"
    assert order.audit_events.get(kind="admin_cancelled").data == {
        "reason": "Cliente solicitó cancelar por duplicado"
    }


@pytest.mark.django_db
@override_settings(CORREO_ARGENTINO_ENABLED=False)
def test_order_admin_provider_failure_is_bounded_and_does_not_leak_diagnostics(
    client, django_user_model
):
    from commerce.models import Cart, CartLine, Shipment

    customer = django_user_model.objects.create_user(email="tracking-buyer@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="TRACKING-FAIL"), quantity=1)
    order = pending_order(cart)
    shipment = Shipment.objects.create(
        order=order,
        provider_id="provider-shipment-1",
        tracking_number="TRACKING-1",
    )
    owner = django_user_model.objects.create_superuser(email="tracking-owner@example.test")
    client.force_login(owner)

    response = client.post(
        "/admin/commerce/order/",
        {
            "action": "refresh_tracking_selected",
            "_selected_action": str(order.pk),
            "index": "0",
            "reason": "Verificación operativa de tracking",
        },
        follow=True,
    )

    shipment.refresh_from_db()
    body = response.content.decode()
    assert response.status_code == 200
    assert shipment.status == "created"
    assert "1 pedido(s) no eran elegibles; no se modificaron." in body
    assert "no está configurado" not in body
    assert not order.audit_events.filter(kind="admin_refresh_tracking_completed").exists()


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
