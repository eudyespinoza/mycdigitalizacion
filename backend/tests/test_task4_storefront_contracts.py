import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from tests.test_commerce_domain import make_variant


@pytest.mark.django_db
def test_registered_customer_can_reach_safe_checkout_through_real_cookie_and_csrf_contracts(
    django_user_model, monkeypatch
):
    del django_user_model
    from locations.providers import GeocodeResult

    class Geocoder:
        def geocode(self, *, street, number, locality, province):
            assert (street, number, locality, province) == (
                "Calle Uno",
                "123",
                "CABA",
                "CABA",
            )
            return GeocodeResult(
                normalized_address="CALLE UNO 123, CABA",
                latitude=Decimal("-34.6037000"),
                longitude=Decimal("-58.3816000"),
                confidence=Decimal("0.950"),
                summary={"provider": "georef"},
            )

    monkeypatch.setattr("api_views.secrets.randbelow", lambda upper: 123456)
    monkeypatch.setattr("api_views.GeoRefAdapter", Geocoder)
    variant = make_variant(sku="JOURNEY-CONTRACT", price="120.00", on_hand=5)
    browser = Client(enforce_csrf_checks=True)
    registered = browser.post(
        "/api/v1/auth/register/",
        {
            "email": "journey@example.test",
            "password": "Correct-Horse-Battery-Staple-42",
            "consent_version": "privacy-v1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone": "+54 11 5555-0199",
        },
        content_type="application/json",
    )
    assert registered.status_code == 201
    verified = browser.post(
        "/api/v1/auth/email-verify/",
        {"email": "journey@example.test", "code": "123456"},
        content_type="application/json",
    )
    assert verified.status_code == 200
    pre_login_csrf = browser.get("/api/v1/auth/csrf/").json()["csrf_token"]
    logged_in = browser.post(
        "/api/v1/auth/login/",
        {"email": "journey@example.test", "password": "Correct-Horse-Battery-Staple-42"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=pre_login_csrf,
    )
    assert logged_in.status_code == 200
    csrf = browser.get("/api/v1/auth/csrf/").json()["csrf_token"]
    profile = browser.patch(
        "/api/v1/customers/me/",
        json.dumps({"dni": "12.345.678"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert profile.status_code == 200
    assert profile.json()["masked_dni"] == "••••5678"
    billing = browser.post(
        "/api/v1/billing-profiles/",
        {
            "label": "Consumidor final",
            "legal_name": "Ada Lovelace",
            "tax_condition": "consumidor_final",
            "cuit": "20-12345678-6",
            "is_default": True,
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert billing.status_code == 201
    address = browser.post(
        "/api/v1/addresses/",
        {
            "label": "Casa",
            "raw_address": "Calle Uno 123",
            "street": "Calle Uno",
            "number": "123",
            "postal_code": "1414",
            "locality": "CABA",
            "province": "CABA",
            "floor": "8",
            "apartment": "B",
            "notes": "No enviar al proveedor",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert address.status_code == 201
    address_id = address.json()["id"]
    geocoded = browser.post(
        "/api/v1/locations/geocode/",
        {"address_id": address_id},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert geocoded.status_code == 200
    confirmed = browser.post(
        f"/api/v1/addresses/{address_id}/confirm/",
        {
            "latitude": geocoded.json()["latitude"],
            "longitude": geocoded.json()["longitude"],
            "address_choice": "written",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["needs_review"] is False
    cart = browser.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 1},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert cart.status_code == 201
    assert cart.json()["lines"][0]["line_total"] == "120.00"
    checkout = browser.post(
        "/api/v1/checkout/",
        {
            "fulfillment_method": "pickup",
            "billing_profile_id": billing.json()["id"],
            "consent": True,
            "idempotency_key": "b0eb858b-5d5a-41f2-935d-dcf7fc79a42d",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert checkout.status_code == 202
    assert checkout.json()["identity_status"] == "pending_identity"
    assert checkout.json()["checkout_url"] == ""


def verified_user(django_user_model, email="storefront-contract@example.test"):
    from accounts.models import CustomerProfile, Profile

    user = django_user_model.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-Staple-42",
        email_verified_at=timezone.now(),
    )
    Profile.objects.create(user=user)
    CustomerProfile.objects.create(user=user, consent_version="privacy-v1")
    return user


@pytest.mark.django_db
def test_registration_accepts_and_persists_checkout_profile_fields(client):
    payload = {
        "email": "new-customer@example.test",
        "password": "Correct-Horse-Battery-Staple-42",
        "consent_version": "privacy-v1",
        "first_name": "  Ada  ",
        "last_name": "  Lovelace  ",
        "phone": "+54 11 5555-0199",
    }

    response = client.post("/api/v1/auth/register/", payload, content_type="application/json")

    assert response.status_code == 201
    assert response.json()["profile"] == {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone": "+54 11 5555-0199",
    }
    missing = client.post(
        "/api/v1/auth/register/",
        {
            "email": "missing-profile@example.test",
            "password": "Correct-Horse-Battery-Staple-42",
            "consent_version": "privacy-v1",
        },
        content_type="application/json",
    )
    assert missing.status_code == 201
    assert missing.json()["profile"] == {"first_name": "", "last_name": "", "phone": ""}


@pytest.mark.django_db
def test_profile_patch_requires_csrf_and_returns_only_masked_dni(django_user_model):
    user = verified_user(django_user_model)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    payload = json.dumps(
        {
            "first_name": "Grace",
            "last_name": "Hopper",
            "phone": "+54 11 4444-0101",
            "dni": "12.345.678",
        }
    )

    rejected = csrf_client.patch(
        "/api/v1/customers/me/", payload, content_type="application/json"
    )
    token = csrf_client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    response = csrf_client.patch(
        "/api/v1/customers/me/",
        payload,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )

    assert rejected.status_code == 403
    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == {
        "first_name": "Grace",
        "last_name": "Hopper",
        "phone": "+54 11 4444-0101",
    }
    assert body["masked_dni"] == "••••5678"
    encoded = response.content.decode()
    assert "12345678" not in encoded
    assert "dni_hash" not in encoded
    assert "dni_encrypted" not in encoded
    user.customer_profile.refresh_from_db()
    assert user.customer_profile.get_dni() == "12345678"


@pytest.mark.django_db
def test_profile_patch_rejects_invalid_dni_without_overwriting_existing_value(
    client, django_user_model
):
    user = verified_user(django_user_model, "dni-validation@example.test")
    user.customer_profile.set_dni("12345678")
    user.customer_profile.save(update_fields=("dni_encrypted", "dni_hash"))
    client.force_login(user)

    response = client.patch(
        "/api/v1/customers/me/", {"dni": "123"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert set(response.json()) == {"dni"}
    user.customer_profile.refresh_from_db()
    assert user.customer_profile.get_dni() == "12345678"


def make_address(user, **overrides):
    from locations.models import Address

    values = {
        "user": user,
        "label": "Casa",
        "raw_address": "Calle Uno 123",
        "street": "Calle Uno",
        "number": "123",
        "postal_code": "1414",
        "locality": "CABA",
        "province": "CABA",
        "latitude": Decimal("-34.6037000"),
        "longitude": Decimal("-58.3816000"),
        "geocode_source": Address.GeocodeSource.GEOREF,
        "needs_review": True,
        "floor": "8",
        "apartment": "B",
        "notes": "timbre roto",
    }
    values.update(overrides)
    return Address.objects.create(**values)


@pytest.mark.django_db
def test_address_confirm_accepts_only_owner_persisted_geocode_coordinates(
    client, django_user_model
):
    owner = verified_user(django_user_model, "address-confirm@example.test")
    other = verified_user(django_user_model, "address-other@example.test")
    address = make_address(owner)
    del client
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(other)
    other_token = csrf_client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    hidden = csrf_client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6037000",
            "longitude": "-58.3816000",
            "address_choice": "written",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=other_token,
    )
    assert hidden.status_code == 404

    csrf_client.force_login(owner)
    rejected_csrf = csrf_client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6037000",
            "longitude": "-58.3816000",
            "address_choice": "written",
        },
        content_type="application/json",
    )
    owner_token = csrf_client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    changed = csrf_client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6000000",
            "longitude": "-58.3800000",
            "address_choice": "written",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=owner_token,
    )
    assert rejected_csrf.status_code == 403
    assert changed.status_code == 409
    assert changed.json()["code"] == "address_coordinates_changed"

    confirmed = csrf_client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6037001",
            "longitude": "-58.3816001",
            "address_choice": "written",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=owner_token,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["needs_review"] is False
    assert confirmed.json()["reviewed_at"]
    address.refresh_from_db()
    assert address.geocode_summary["confirmation"]["address_choice"] == "written"
    assert "floor" not in address.geocode_summary["confirmation"]
    assert "apartment" not in address.geocode_summary["confirmation"]
    assert "notes" not in address.geocode_summary["confirmation"]


@pytest.mark.django_db
def test_address_confirm_supports_second_confirmation_after_reverse_lookup(
    client, django_user_model
):
    user = verified_user(django_user_model, "reverse-confirm@example.test")
    address = make_address(
        user,
        latitude=Decimal("-34.6100000"),
        longitude=Decimal("-58.3900000"),
        geocode_source="manual",
        geocode_summary={"provider": "georef", "kind": "reverse"},
    )
    client.force_login(user)

    wrong_choice = client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6100000",
            "longitude": "-58.3900000",
            "address_choice": "written",
        },
        content_type="application/json",
    )
    confirmed = client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6100000",
            "longitude": "-58.3900000",
            "address_choice": "reverse",
        },
        content_type="application/json",
    )

    assert wrong_choice.status_code == 409
    assert wrong_choice.json()["code"] == "address_choice_mismatch"
    assert confirmed.status_code == 200
    assert confirmed.json()["needs_review"] is False


@pytest.mark.django_db
def test_address_confirm_rejects_coordinates_not_created_by_a_geocode_flow(
    client, django_user_model
):
    user = verified_user(django_user_model, "ungeocoded-confirm@example.test")
    address = make_address(user, geocode_source="")
    client.force_login(user)

    response = client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": str(address.latitude),
            "longitude": str(address.longitude),
            "address_choice": "written",
        },
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "address_not_geocoded"

    missing = make_address(
        user,
        label="Sin coordenadas",
        latitude=None,
        longitude=None,
        geocode_source="georef",
    )
    missing_response = client.post(
        f"/api/v1/addresses/{missing.pk}/confirm/",
        {
            "latitude": "-34.6037000",
            "longitude": "-58.3816000",
            "address_choice": "written",
        },
        content_type="application/json",
    )
    assert missing_response.status_code == 409
    assert missing_response.json()["code"] == "address_coordinates_missing"


@pytest.mark.django_db
def test_public_catalog_and_landing_media_urls_are_same_origin_relative(
    client, settings, tmp_path
):
    from catalog.models import ProductMedia
    from landing.models import HeroSlide

    settings.MEDIA_URL = "/media/"
    settings.MEDIA_ROOT = tmp_path
    variant = make_variant(sku="MEDIA-CONTRACT")
    ProductMedia.objects.create(
        product=variant.product,
        file=SimpleUploadedFile("product.jpg", b"image"),
        alt_text="Producto sintético",
    )
    HeroSlide.objects.create(
        title="Hero",
        alt_text="Campaña sintética",
        desktop_image=SimpleUploadedFile("hero.jpg", b"image"),
    )

    product = client.get("/api/v1/products/").json()["results"][0]
    home = client.get("/api/v1/storefront/home/").json()

    assert product["media"][0]["file"].startswith("/media/")
    assert home["hero_slides"][0]["desktop_image_url"].startswith("/media/")
    assert "backend:8000" not in json.dumps({"product": product, "home": home})
    assert "http://" not in product["media"][0]["file"]


@pytest.mark.django_db
def test_catalog_contract_filters_descendants_offers_stock_brand_and_typed_attributes(client):
    from catalog.models import (
        AttributeDefinition,
        AttributeValue,
        Brand,
        Category,
    )
    from commerce.models import PromotionRule

    root = Category.objects.create(name="Tecnología", slug="tecnologia")
    child = Category.objects.create(name="Audio", slug="audio", parent=root)
    brand = Brand.objects.create(name="Acme", slug="acme")
    variant = make_variant(sku="CATALOG-CONTRACT", price="100.00", on_hand=4)
    product = variant.product
    product.category = child
    product.brand = brand
    product._allow_activation = True
    product.save(update_fields=("category", "brand"))
    definition = AttributeDefinition.objects.create(
        name="Potencia", slug="potencia", value_type="integer", is_filterable=True
    )
    AttributeValue.objects.create(variant=variant, definition=definition, integer_value=20)
    now = timezone.now()
    promotion = PromotionRule.objects.create(
        name="Oferta 25",
        discount_type="percentage",
        value=Decimal("25"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    promotion.products.add(product)

    response = client.get(
        "/api/v1/products/?category=tecnologia&brand=acme&availability=in_stock"
        "&offer=true&min_price=70&max_price=80&attribute_potencia=20"
        "&ordering=discount_desc&page=1&page_size=12"
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results", "facets"}
    assert body["count"] == 1
    result = body["results"][0]
    assert result["brand"] == {"name": "Acme", "slug": "acme"}
    public_variant = result["variants"][0]
    assert public_variant["available_stock"] == 4
    assert public_variant["attributes"] == [
        {"name": "Potencia", "slug": "potencia", "type": "integer", "value": 20}
    ]
    assert public_variant["pricing"] == {
        "list_price": "100.00",
        "effective_price": "75.00",
        "discount_amount": "25.00",
        "discount_percentage": "25.00",
        "on_offer": True,
    }
    assert "cost" not in json.dumps(result)
    assert body["facets"]["price"] == {"min": "75.00", "max": "75.00"}
    assert body["facets"]["attributes"][0]["values"][0]["value"] == 20
    assert body["facets"]["categories"][0]["children"][0]["slug"] == "audio"


@pytest.mark.django_db
def test_search_uses_same_documented_envelope_and_search_alias(client):
    make_variant(sku="SEARCH-ALIAS")

    response = client.get("/api/v1/search/?search=Producto&page_size=1")

    assert response.status_code == 200
    assert set(response.json()) == {"count", "next", "previous", "results", "facets"}
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_catalog_newest_ordering_uses_product_creation_time(client):
    older = make_variant(sku="ORDER-OLDER").product
    newer = make_variant(sku="ORDER-NEWER").product
    type(older).objects.filter(pk=older.pk).update(
        created_at=timezone.now() + timezone.timedelta(days=1)
    )

    response = client.get("/api/v1/products/?ordering=newest")

    assert [item["slug"] for item in response.json()["results"]] == [older.slug, newer.slug]


@pytest.mark.django_db
def test_catalog_price_range_must_match_one_real_variant(client):
    from catalog.models import ProductVariant

    first = make_variant(sku="RANGE-LOW", price="50.00")
    ProductVariant.objects.create(
        product=first.product,
        sku="RANGE-HIGH",
        price=Decimal("150.00"),
        cost=Decimal("10.00"),
        packaged_weight_grams=500,
        length_cm=Decimal("10"),
        width_cm=Decimal("10"),
        height_cm=Decimal("10"),
        on_hand=3,
    )

    response = client.get("/api/v1/products/?min_price=70&max_price=130")

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_catalog_dynamic_attribute_filters_use_declared_value_type(client):
    from catalog.models import AttributeDefinition, AttributeValue

    variant = make_variant(sku="TYPED-FILTER")
    definition = AttributeDefinition.objects.create(
        name="Peso neto", slug="peso-neto", value_type="decimal", is_filterable=True
    )
    AttributeValue.objects.create(
        variant=variant,
        definition=definition,
        decimal_value=Decimal("1.2000"),
    )

    matching = client.get("/api/v1/products/?attribute_peso-neto=1.2")
    invalid = client.get("/api/v1/products/?attribute_peso-neto=no-es-decimal")

    assert matching.status_code == 200
    assert matching.json()["count"] == 1
    assert invalid.status_code == 400
    assert set(invalid.json()) == {"attribute_peso-neto"}


@pytest.mark.django_db
def test_cart_lines_publish_authoritative_amounts_stock_and_stable_change_notices(client):
    variant = make_variant(sku="CART-CONTRACT", price="80.00", on_hand=3)
    created = client.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 2},
        content_type="application/json",
    )
    assert created.status_code == 201
    token = created.json()["cart_token"]
    line = created.json()["lines"][0]
    assert line["line_subtotal"] == "160.00"
    assert line["line_discount"] == "0.00"
    assert line["line_total"] == "160.00"
    assert line["availability"] == "available"
    assert line["available_stock"] == 3
    assert line["notices"] == []

    variant.price = Decimal("100.00")
    variant.on_hand = 1
    variant.save(update_fields=("price", "on_hand"))
    refreshed = client.get("/api/v1/cart/", HTTP_X_CART_TOKEN=token)
    changed = refreshed.json()["lines"][0]

    assert changed["line_total"] == "200.00"
    assert changed["availability"] == "insufficient_stock"
    assert changed["notices"] == [
        {"code": "price_changed", "previous": "80.00", "current": "100.00"},
        {"code": "stock_changed", "previous": 3, "current": 1},
    ]


@pytest.mark.django_db
def test_order_detail_has_bounded_safe_timeline_shipment_and_configured_pickup(
    client, django_user_model
):
    from commerce.models import Cart, CartLine, OrderAuditEvent, Shipment
    from commerce.services import create_pending_identity_order, transition_order_status
    from landing.models import SiteSettings

    user = verified_user(django_user_model, "order-contract@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="ORDER-CONTRACT"), quantity=1)
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )
    transition_order_status(order=order, field="payment_status", value="paid")
    OrderAuditEvent.objects.create(
        order=order,
        kind="internal_provider_diagnostic",
        data={"provider_secret": "never-public"},
    )
    Shipment.objects.create(
        order=order,
        provider_id="provider-secret-id",
        tracking_number="TRACK-123",
        status="created",
        provider_summary={"secret": "never-public"},
    )
    SiteSettings.objects.create(
        pickup_enabled=True,
        pickup_label="Retiro en depósito",
        pickup_address="Calle Segura 123, CABA",
        pickup_hours="Lunes a viernes de 9 a 17",
    )
    client.force_login(user)

    response = client.get(f"/api/v1/orders/{order.public_id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["shipment"] == {
        "carrier": "correo_argentino",
        "tracking_number": "TRACK-123",
        "status": "created",
        "updated_at": body["shipment"]["updated_at"],
    }
    assert body["pickup_information"] == {
        "enabled": True,
        "label": "Retiro en depósito",
        "address": "Calle Segura 123, CABA",
        "hours": "Lunes a viernes de 9 a 17",
    }
    assert [event["status"] for event in body["timeline"]] == [
        "order_created",
        "payment_paid",
    ]
    encoded = response.content.decode()
    assert "provider-secret-id" not in encoded
    assert "provider_secret" not in encoded
    assert "never-public" not in encoded


@pytest.mark.django_db
def test_openapi_publishes_task4_storefront_write_and_catalog_contracts(client):
    schema = client.get("/api/v1/schema/?format=json").json()
    paths = schema["paths"]
    assert "/api/v1/addresses/{id}/confirm/" in paths
    assert "patch" in paths["/api/v1/customers/me/"]
    register_schema = paths["/api/v1/auth/register/"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    register = schema["components"]["schemas"][register_schema["$ref"].rsplit("/", 1)[-1]]
    assert set(register["required"]) == {"email", "password", "consent_version"}
    assert {"first_name", "last_name", "phone"} <= set(register["properties"])
    query_names = {
        parameter["name"]
        for parameter in paths["/api/v1/products/"]["get"].get("parameters", [])
    }
    assert {
        "q",
        "search",
        "category",
        "brand",
        "min_price",
        "max_price",
        "availability",
        "offer",
        "ordering",
        "page",
        "page_size",
    } <= query_names
