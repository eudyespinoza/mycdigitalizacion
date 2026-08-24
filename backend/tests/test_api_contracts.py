import pytest
from django.urls import reverse
from django.utils import timezone

from commerce.services import create_pending_identity_order
from tests.test_commerce_domain import make_variant


@pytest.mark.django_db
def test_public_product_api_never_exposes_cost(client):
    make_variant(price="120.00", cost="17.50")

    response = client.get("/api/v1/products/")

    assert response.status_code == 200
    assert response.json()["results"][0]["variants"][0]["price"] == "120.00"
    assert "cost" not in response.json()["results"][0]["variants"][0]
    assert "17.50" not in response.content.decode()


@pytest.mark.django_db
def test_cart_uses_server_price_and_returns_decimal_string_totals(client):
    variant = make_variant(price="41.25")

    response = client.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 2, "price": "0.01"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["subtotal"] == "82.50"
    assert response.json()["discount"] == "0.00"
    assert response.json()["total"] == "82.50"
    assert response.json()["cart_token"]


@pytest.mark.django_db
def test_order_detail_is_only_visible_to_its_owner(client, django_user_model):
    owner = django_user_model.objects.create_user(
        email="owner@example.test", password="pass", email_verified_at=timezone.now()
    )
    other = django_user_model.objects.create_user(
        email="other@example.test", password="pass", email_verified_at=timezone.now()
    )
    from commerce.models import Cart, CartLine

    cart = Cart.objects.create(user=owner)
    CartLine.objects.create(cart=cart, variant=make_variant(), quantity=1)
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": owner.email},
        address_snapshot={"street": "Sintetica"},
        fiscal_snapshot={"condition": "consumidor_final"},
        fulfillment_method="shipping",
    )
    client.force_login(owner)
    assert client.get(f"/api/v1/orders/{order.public_id}/").status_code == 200
    client.force_login(other)

    response = client.get(f"/api/v1/orders/{order.public_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_address_crud_is_scoped_to_authenticated_owner(client, django_user_model):
    from locations.models import Address

    owner = django_user_model.objects.create_user(
        email="address-owner@example.test", email_verified_at=timezone.now()
    )
    other = django_user_model.objects.create_user(
        email="address-other@example.test", email_verified_at=timezone.now()
    )
    address = Address.objects.create(
        user=owner,
        label="Casa sintetica",
        raw_address="Calle Sintetica 123",
        street="Calle Sintetica",
        number="123",
        postal_code="1000",
        locality="CABA",
        province="CABA",
    )
    client.force_login(owner)
    assert client.get(f"/api/v1/addresses/{address.pk}/").status_code == 200
    client.force_login(other)

    response = client.get(f"/api/v1/addresses/{address.pk}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_identity_and_checkout_boundaries_require_checkout_input(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="boundary@example.test", email_verified_at=timezone.now()
    )
    client.force_login(user)

    identity = client.get("/api/v1/identity/status/")
    checkout = client.post("/api/v1/checkout/", {}, content_type="application/json")

    assert identity.status_code == 200
    assert identity.json() == {"status": "not_required", "required": False}
    assert checkout.status_code == 400
    assert checkout.json() == {
        "fulfillment_method": ["Este campo es requerido."],
        "billing_profile_id": ["Este campo es requerido."],
        "consent": ["Este campo es requerido."],
        "idempotency_key": ["Este campo es requerido."],
    }


@pytest.mark.django_db
def test_openapi_schema_is_available(client):
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    assert b"openapi" in response.content
