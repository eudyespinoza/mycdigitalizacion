import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from catalog.models import (
    AttributeDefinition,
    AttributeOption,
    Brand,
    Category,
    ProductMedia,
    ProductVariant,
)
from commerce.models import InventoryMovement

pytestmark = pytest.mark.django_db


def management_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="catalog-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(owner)
    return client


def test_management_product_creation_uses_variants_and_audited_initial_stock(
    django_user_model,
):
    category = Category.objects.create(name="Librería", slug="libreria")
    brand = Brand.objects.create(name="myc", slug="myc")
    client = management_client(django_user_model)

    response = client.post(
        "/api/v1/management/products/",
        {
            "name": "Cuaderno A5",
            "slug": "cuaderno-a5",
            "description": "Cuaderno rayado de 80 hojas.",
            "category_id": category.pk,
            "brand_id": brand.pk,
            "publish": True,
            "variants": [
                {
                    "sku": "CUA-A5-AZUL",
                    "name": "Azul",
                    "price": "4890.00",
                    "cost": "2600.00",
                    "on_hand": 12,
                    "packaged_weight_grams": 330,
                    "length_cm": "21.00",
                    "width_cm": "15.00",
                    "height_cm": "2.00",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sellable"] is True
    assert body["variants"][0]["cost"] == "2600.00"
    assert body["variants"][0]["on_hand"] == 12
    variant = ProductVariant.objects.get(sku="CUA-A5-AZUL")
    movement = InventoryMovement.objects.get(variant=variant)
    assert movement.quantity_delta == 12
    assert movement.source == "domain"
    assert movement.actor.email == "catalog-owner@example.test"


def test_management_product_update_keeps_existing_sku_and_adds_a_variant(
    django_user_model,
):
    category = Category.objects.create(name="Cuadernos", slug="cuadernos")
    client = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/products/",
        {
            "name": "Libreta tapa dura",
            "slug": "libreta-tapa-dura",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "MYC-LIB-TAP-80",
                    "name": "80 Hojas",
                    "price": "9750.00",
                    "cost": "5100.00",
                    "on_hand": 25,
                    "packaged_weight_grams": 140,
                    "length_cm": "22.00",
                    "width_cm": "8.00",
                    "height_cm": "7.00",
                }
            ],
        },
        format="json",
    )
    existing = created.json()["variants"][0]

    response = client.patch(
        f"/api/v1/management/products/{created.json()['id']}/",
        {
            "variants": [
                {
                    "id": existing["id"],
                    "sku": "MYC-LIB-TAP-80",
                    "name": "80 Hojas",
                    "price": "9750.00",
                    "cost": "5100.00",
                    "on_hand": 25,
                    "packaged_weight_grams": 140,
                    "length_cm": "22.00",
                    "width_cm": "8.00",
                    "height_cm": "7.00",
                },
                {
                    "sku": "MYC-LIB-TAP-60",
                    "name": "60 Hojas",
                    "price": "7650.00",
                    "cost": "3500.00",
                    "on_hand": 15,
                    "packaged_weight_grams": 126,
                    "length_cm": "22.00",
                    "width_cm": "18.00",
                    "height_cm": "4.00",
                },
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert [variant["sku"] for variant in response.json()["variants"]] == [
        "MYC-LIB-TAP-80",
        "MYC-LIB-TAP-60",
    ]
    assert ProductVariant.objects.filter(product_id=created.json()["id"]).count() == 2


def test_management_product_list_searches_real_catalog_and_includes_cost(django_user_model):
    category = Category.objects.create(name="Escritura", slug="escritura")
    client = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/products/",
        {
            "name": "Resaltador pastel",
            "slug": "resaltador-pastel",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "RES-PASTEL",
                    "name": "Set x6",
                    "price": "6450.00",
                    "cost": "3900.00",
                    "on_hand": 4,
                    "packaged_weight_grams": 160,
                    "length_cm": "18.00",
                    "width_cm": "10.00",
                    "height_cm": "3.00",
                }
            ],
        },
        format="json",
    )
    assert created.status_code == 201

    response = client.get("/api/v1/management/products/?search=resaltador")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["variants"][0]["cost"] == "3900.00"


def test_stock_adjustment_requires_reason_and_creates_movement(django_user_model):
    category = Category.objects.create(name="Oficina", slug="oficina")
    client = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/products/",
        {
            "name": "Organizador",
            "slug": "organizador",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "ORG-001",
                    "name": "Único",
                    "price": "12900.00",
                    "cost": "7000.00",
                    "on_hand": 2,
                    "packaged_weight_grams": 800,
                    "length_cm": "30.00",
                    "width_cm": "20.00",
                    "height_cm": "15.00",
                }
            ],
        },
        format="json",
    )
    assert created.status_code == 201
    product = created.json()
    variant_id = product["variants"][0]["id"]

    missing_reason = client.post(
        f"/api/v1/management/variants/{variant_id}/adjust-stock/",
        {"new_on_hand": 7, "reason": ""},
        format="json",
    )
    assert missing_reason.status_code == 400

    adjusted = client.post(
        f"/api/v1/management/variants/{variant_id}/adjust-stock/",
        {"new_on_hand": 7, "reason": "Ingreso de mercadería"},
        format="json",
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["on_hand"] == 7
    assert InventoryMovement.objects.filter(variant_id=variant_id).count() == 2


def test_management_category_and_brand_endpoints_are_not_django_admin(django_user_model):
    client = management_client(django_user_model)
    parent = client.post(
        "/api/v1/management/categories/",
        {"name": "Librería", "slug": "libreria", "is_active": True},
        format="json",
    )
    assert parent.status_code == 201
    child = client.post(
        "/api/v1/management/categories/",
        {
            "name": "Cuadernos",
            "slug": "cuadernos",
            "parent_id": parent.json()["id"],
            "is_active": True,
        },
        format="json",
    )
    brand = client.post(
        "/api/v1/management/brands/",
        {"name": "myc Selección", "slug": "myc-seleccion"},
        format="json",
    )

    assert child.status_code == 201
    assert child.json()["parent_id"] == parent.json()["id"]
    assert brand.status_code == 201
    assert client.get("/api/v1/management/categories/").json()["results"][1]["name"] == "Cuadernos"


def test_customer_cannot_access_management_catalog(django_user_model):
    customer = django_user_model.objects.create_user(
        email="customer-catalog@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(customer)
    assert client.get("/api/v1/management/products/").status_code == 403


def test_management_product_supports_multiple_variants_and_filter_attributes(
    django_user_model,
):
    category = Category.objects.create(name="Mochilas", slug="mochilas")
    color = AttributeDefinition.objects.create(
        name="Color",
        slug="color",
        value_type=AttributeDefinition.ValueType.OPTION,
        is_filterable=True,
    )
    AttributeOption.objects.create(definition=color, label="Azul", value="azul")
    AttributeOption.objects.create(definition=color, label="Rosa", value="rosa")
    client = management_client(django_user_model)

    response = client.post(
        "/api/v1/management/products/",
        {
            "name": "Mochila urbana",
            "slug": "mochila-urbana",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "MOC-AZUL",
                    "name": "Azul",
                    "price": "35000.00",
                    "cost": "21000.00",
                    "on_hand": 5,
                    "packaged_weight_grams": 800,
                    "length_cm": "45.00",
                    "width_cm": "30.00",
                    "height_cm": "18.00",
                    "attribute_values": [{"definition_id": color.pk, "value": "azul"}],
                },
                {
                    "sku": "MOC-ROSA",
                    "name": "Rosa",
                    "price": "35000.00",
                    "cost": "21000.00",
                    "on_hand": 3,
                    "packaged_weight_grams": 800,
                    "length_cm": "45.00",
                    "width_cm": "30.00",
                    "height_cm": "18.00",
                    "attribute_values": [{"definition_id": color.pk, "value": "rosa"}],
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    assert [variant["sku"] for variant in response.json()["variants"]] == [
        "MOC-AZUL",
        "MOC-ROSA",
    ]
    assert response.json()["variants"][0]["attributes"] == [
        {
            "definition_id": color.pk,
            "name": "Color",
            "slug": "color",
            "value_type": "option",
            "value": "azul",
        }
    ]


def test_management_product_image_upload_update_and_delete(
    django_user_model,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_RESPONSIVE_WIDTHS = (32,)
    category = Category.objects.create(name="Arte", slug="arte")
    client = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/products/",
        {
            "name": "Set artístico",
            "slug": "set-artistico",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "ART-001",
                    "name": "Único",
                    "price": "12000.00",
                    "cost": "7000.00",
                    "on_hand": 4,
                    "packaged_weight_grams": 500,
                    "length_cm": "30.00",
                    "width_cm": "20.00",
                    "height_cm": "5.00",
                }
            ],
        },
        format="json",
    )
    product_id = created.json()["id"]
    variant_id = created.json()["variants"][0]["id"]
    image = io.BytesIO()
    Image.new("RGB", (64, 48), "#08aecd").save(image, format="PNG")
    upload = SimpleUploadedFile("producto.png", image.getvalue(), content_type="image/png")

    uploaded = client.post(
        f"/api/v1/management/products/{product_id}/media/",
        {
            "file": upload,
            "alt_text": "Set artístico abierto",
            "order": 1,
            "variant_id": variant_id,
        },
        format="multipart",
    )

    assert uploaded.status_code == 201
    media_id = uploaded.json()["id"]
    assert uploaded.json()["file_url"].startswith("/media/catalog/")
    assert uploaded.json()["variant_id"] == variant_id
    assert uploaded.json()["variant_name"] == "Único"
    assert uploaded.json()["responsive_sources"]
    updated = client.patch(
        f"/api/v1/management/products/{product_id}/media/{media_id}/",
        {"alt_text": "Contenido completo del set", "order": 0, "variant_id": None},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["alt_text"] == "Contenido completo del set"
    assert updated.json()["variant_id"] is None
    deleted = client.delete(
        f"/api/v1/management/products/{product_id}/media/{media_id}/"
    )
    assert deleted.status_code == 204
    assert not ProductMedia.objects.filter(pk=media_id).exists()
