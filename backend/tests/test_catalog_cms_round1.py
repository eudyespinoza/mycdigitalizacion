from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.test_commerce_domain import make_variant


@pytest.mark.django_db
def test_category_subtree_move_rejects_depth_six_and_cycles():
    from catalog.models import Category
    from catalog.services import move_category

    root = Category.objects.create(name="Raíz", slug="move-root")
    child = Category.objects.create(name="Hija", slug="move-child", parent=root)
    grandchild = Category.objects.create(name="Nieta", slug="move-grandchild", parent=child)
    parent = Category.objects.create(name="Destino", slug="move-destination")
    parent2 = Category.objects.create(name="Destino 2", slug="move-destination-2", parent=parent)
    parent3 = Category.objects.create(name="Destino 3", slug="move-destination-3", parent=parent2)

    with pytest.raises(ValidationError, match="five levels"):
        move_category(category=root, new_parent=parent3)
    with pytest.raises(ValidationError, match="cycle"):
        move_category(category=root, new_parent=grandchild)

    move_category(category=root, new_parent=parent)
    root.refresh_from_db()
    assert root.parent == parent


@pytest.mark.django_db
def test_category_parent_cannot_be_mutated_outside_reparent_service():
    from catalog.models import Category

    root = Category.objects.create(name="Directa", slug="direct-root")
    parent = Category.objects.create(name="Padre", slug="direct-parent")
    root.parent = parent
    with pytest.raises(ValidationError, match="move_category"):
        root.save()
    with pytest.raises(ValidationError, match="move_category"):
        Category.objects.filter(pk=root.pk).update(parent=parent)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("value_type", "field", "value"),
    [
        ("text", "text_value", "Azul"),
        ("integer", "integer_value", 42),
        ("decimal", "decimal_value", Decimal("1.2500")),
        ("boolean", "boolean_value", False),
    ],
)
def test_attribute_value_accepts_exactly_the_declared_type(value_type, field, value):
    from catalog.models import AttributeDefinition, AttributeValue

    variant = make_variant(sku=f"ATTR-{value_type.upper()}")
    definition = AttributeDefinition.objects.create(
        name=value_type, slug=f"attr-{value_type}", value_type=value_type
    )
    attribute = AttributeValue(variant=variant, definition=definition, **{field: value})

    attribute.full_clean()
    attribute.save()
    assert attribute.pk


@pytest.mark.django_db
def test_option_attribute_requires_option_from_same_definition():
    from catalog.models import AttributeDefinition, AttributeOption, AttributeValue

    variant = make_variant(sku="ATTR-OPTION")
    definition = AttributeDefinition.objects.create(
        name="Color", slug="attr-color", value_type="option"
    )
    other = AttributeDefinition.objects.create(
        name="Talle", slug="attr-size", value_type="option"
    )
    wrong_option = AttributeOption.objects.create(definition=other, label="L", value="l")

    with pytest.raises(ValidationError, match="same definition"):
        AttributeValue(
            variant=variant, definition=definition, option=wrong_option
        ).full_clean()


@pytest.mark.django_db
def test_attribute_value_rejects_empty_or_multiple_storage_fields_at_database():
    from catalog.models import AttributeDefinition, AttributeValue

    variant = make_variant(sku="ATTR-DB")
    definition = AttributeDefinition.objects.create(
        name="Peso", slug="attr-weight", value_type="integer"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        AttributeValue._base_manager.bulk_create(
            [AttributeValue(variant=variant, definition=definition)]
        )


@pytest.mark.django_db
def test_last_active_variant_cannot_be_deactivated_or_deleted_for_sellable_product():
    from catalog.services import delete_variant, set_variant_active

    variant = make_variant(sku="LAST-ACTIVE")

    with pytest.raises(ValidationError, match="last active"):
        set_variant_active(variant=variant, active=False)
    with pytest.raises(ValidationError, match="last active"):
        type(variant).objects.filter(pk=variant.pk).update(is_active=False)
    with pytest.raises(ValidationError, match="last active"):
        delete_variant(variant=variant)
    with pytest.raises(ValidationError, match="last active"):
        type(variant).objects.filter(pk=variant.pk).delete()


@pytest.mark.django_db
def test_public_catalog_and_cart_exclude_draft_or_inactive_variants(client):
    from catalog.models import ProductVariant

    sellable = make_variant(sku="PUBLIC-ACTIVE")
    inactive = ProductVariant.objects.create(
        product=sellable.product,
        sku="PUBLIC-INACTIVE",
        price=Decimal("100"),
        cost=Decimal("50"),
        packaged_weight_grams=1,
        length_cm=Decimal("1"),
        width_cm=Decimal("1"),
        height_cm=Decimal("1"),
        is_active=False,
    )
    draft = make_variant(sku="PUBLIC-DRAFT")
    draft.product.is_sellable = False
    draft.product.save(update_fields=["is_sellable"])

    detail = client.get(f"/api/v1/products/{sellable.product.slug}/")
    assert detail.status_code == 200
    assert detail.json()["sku"] == sellable.product.sku
    assert [item["sku"] for item in detail.json()["variants"]] == ["PUBLIC-ACTIVE"]
    assert client.get(f"/api/v1/products/{draft.product.slug}/").status_code == 404
    assert client.post("/api/v1/cart/", {"variant_id": inactive.pk}).status_code == 400
    assert client.post("/api/v1/cart/", {"variant_id": draft.pk}).status_code == 400


@pytest.mark.django_db
def test_money_dimensions_discounts_and_schedules_reject_invalid_values():
    from catalog.models import ProductVariant
    from commerce.models import PromotionRule

    variant = make_variant(sku="INVALID-MONEY")
    variant.price = Decimal("-0.01")
    variant.length_cm = Decimal("0")
    with pytest.raises(ValidationError):
        variant.full_clean()

    now = timezone.now()
    promotion = PromotionRule(
        name="Inválida",
        discount_type="percentage",
        value=Decimal("150"),
        starts_at=now,
        ends_at=now - timezone.timedelta(seconds=1),
    )
    with pytest.raises(ValidationError):
        promotion.full_clean()

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariant.objects.filter(pk=variant.pk).update(price=Decimal("-1"))


@pytest.mark.django_db
def test_cms_home_exposes_media_layout_body_and_collection_fields(client):
    from landing.models import (
        HeroSlide,
        LandingCollection,
        PromotionPopup,
        PromotionSlide,
        SiteSettings,
    )

    shared = {
        "alt_text": "Imagen sintética",
        "desktop_image": "landing/desktop/example.png",
        "mobile_image": "landing/mobile/example.png",
        "cta_label": "Ver colección",
        "cta_url": "/productos",
        "focal_x": 25,
        "focal_y": 75,
        "safe_height_mobile": 300,
        "safe_height_tablet": 400,
        "safe_height_desktop": 500,
    }
    HeroSlide.objects.create(title="Hero", body="Hero body", **shared)
    PromotionSlide.objects.create(title="Promo", body="Promo body", **shared)
    LandingCollection.objects.create(title="Colección", product_ids=[1, 2], **shared)
    PromotionPopup.objects.create(title="Popup", body="Popup body", **shared)
    SiteSettings.objects.create(contact_email="synthetic-contact@example.test")

    response = client.get("/api/v1/storefront/home/")
    assert response.status_code == 200
    for key in ("hero_slides", "promotion_slides", "collections", "promotion_popups"):
        item = response.json()[key][0]
        assert item["desktop_image_url"].endswith("/media/landing/desktop/example.png")
        assert item["mobile_image_url"].endswith("/media/landing/mobile/example.png")
        assert item["focal_x"] == "25.00"
        assert item["safe_height_desktop"] == 500
    assert response.json()["hero_slides"][0]["body"] == "Hero body"
    assert response.json()["collections"][0]["product_ids"] == [1, 2]
    assert response.json()["settings"]["contact_email"] == "synthetic-contact@example.test"


@pytest.mark.django_db
def test_cms_rejects_invalid_layout_schedule_cta_and_media_extension():
    from landing.models import HeroSlide, LandingCollection

    now = timezone.now()
    slide = HeroSlide(
        title="Inválida",
        alt_text="Inválida",
        desktop_image="landing/desktop/payload.exe",
        focal_x=Decimal("101"),
        safe_height_mobile=0,
        cta_url="javascript:alert(1)",
        starts_at=now,
        ends_at=now - timezone.timedelta(seconds=1),
    )

    with pytest.raises(ValidationError):
        slide.full_clean()
    with pytest.raises(ValidationError, match="product IDs"):
        LandingCollection(
            title="Colección inválida", alt_text="Sintética", product_ids=[1, "2"]
        ).full_clean()


@pytest.mark.django_db
def test_site_settings_is_singleton_and_admin_cannot_add_or_delete(rf):
    from django.contrib.admin.sites import AdminSite

    from landing.admin import SiteSettingsAdmin
    from landing.models import SiteSettings

    first = SiteSettings.objects.create(public_name="Uno")
    second = SiteSettings(public_name="Dos")
    second.save()
    assert SiteSettings.objects.count() == 1
    assert SiteSettings.objects.get().public_name == "Dos"
    model_admin = SiteSettingsAdmin(SiteSettings, AdminSite())
    assert not model_admin.has_add_permission(rf.get("/admin/"))
    assert not model_admin.has_delete_permission(rf.get("/admin/"), first)
