import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from catalog.models import ProductVariant
from tests.test_commerce_domain import make_variant
from tests.test_postgres_round1 import run_concurrently

pytestmark = pytest.mark.django_db


def test_variant_persists_stock_mode_and_optional_per_cart_limit():
    field_names = {field.name for field in ProductVariant._meta.fields}

    assert "stock_is_infinite" in field_names
    assert "max_purchase_quantity" in field_names


def test_database_rejects_zero_as_purchase_limit():
    from django.db import IntegrityError, transaction

    variant = make_variant(sku="ZERO-CAP-GUARD", on_hand=5)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariant.objects.filter(pk=variant.pk).update(max_purchase_quantity=0)


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_cart_additions_cannot_cross_finite_stock():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart
    from commerce.services import PurchaseLimitExceeded, add_cart_line

    cart = Cart.objects.create()
    variant = make_variant(sku="CONCURRENT-FINITE-CAP", on_hand=3)

    outcomes = run_concurrently(
        lambda: add_cart_line(cart=cart, variant=variant, quantity=2).quantity,
        lambda: add_cart_line(cart=cart, variant=variant, quantity=2).quantity,
    )

    assert sum(isinstance(outcome, PurchaseLimitExceeded) for outcome in outcomes) == 1
    assert cart.lines.get(variant=variant).quantity == 2


def test_finite_variant_cannot_exceed_available_stock_in_cart():
    from commerce.models import Cart
    from commerce.services import add_cart_line

    cart = Cart.objects.create()
    variant = make_variant(sku="FINITE-CART-LIMIT", on_hand=2)

    with pytest.raises(ValidationError):
        add_cart_line(cart=cart, variant=variant, quantity=3)

    assert not cart.lines.exists()


def test_optional_purchase_limit_caps_each_cart_for_infinite_stock():
    from commerce.models import Cart
    from commerce.services import add_cart_line

    cart = Cart.objects.create()
    variant = make_variant(sku="INFINITE-CAPPED", on_hand=0)
    variant.stock_is_infinite = True
    variant.max_purchase_quantity = 4
    variant.save(update_fields=("stock_is_infinite", "max_purchase_quantity"))

    add_cart_line(cart=cart, variant=variant, quantity=4)
    with pytest.raises(ValidationError):
        add_cart_line(cart=cart, variant=variant, quantity=1)

    assert cart.lines.get().quantity == 4


def test_infinite_stock_without_purchase_limit_accepts_any_cart_quantity():
    from commerce.models import Cart
    from commerce.services import add_cart_line

    cart = Cart.objects.create()
    variant = make_variant(sku="INFINITE-UNCAPPED", on_hand=0)
    variant.stock_is_infinite = True
    variant.save(update_fields=("stock_is_infinite",))

    line = add_cart_line(cart=cart, variant=variant, quantity=250)

    assert line.quantity == 250


def test_cart_quantity_update_rejects_value_above_effective_limit(client):
    variant = make_variant(sku="PATCH-CAPPED", on_hand=10)
    variant.max_purchase_quantity = 3
    variant.save(update_fields=("max_purchase_quantity",))
    created = client.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 2},
        content_type="application/json",
    )

    response = client.patch(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 4},
        content_type="application/json",
        HTTP_X_CART_TOKEN=created.json()["cart_token"],
    )

    assert response.status_code == 400
    assert response.json()["code"] == "purchase_limit_exceeded"
    refreshed = client.get(
        "/api/v1/cart/",
        HTTP_X_CART_TOKEN=created.json()["cart_token"],
    )
    assert refreshed.json()["lines"][0]["quantity"] == 2


def test_cart_payload_uses_product_and_variant_names(client):
    variant = make_variant(sku="INTERNAL-SKU", on_hand=5)
    variant.product.name = "Libreta tapa dura"
    variant.product.save(update_fields=("name",))
    variant.name = "80 Hojas"
    variant.save(update_fields=("name",))

    response = client.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 1},
        content_type="application/json",
    )

    line = response.json()["lines"][0]
    assert line["product_name"] == "Libreta tapa dura"
    assert line["variant_name"] == "80 Hojas"


def test_cart_merge_never_exceeds_the_per_cart_purchase_limit(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import merge_carts

    user = django_user_model.objects.create_user(email="limited-merge@example.test")
    variant = make_variant(sku="MERGE-CAPPED", on_hand=10)
    variant.max_purchase_quantity = 3
    variant.save(update_fields=("max_purchase_quantity",))
    destination = Cart.objects.create(user=user)
    CartLine.objects.create(cart=destination, variant=variant, quantity=2)
    anonymous = Cart.objects.create()
    CartLine.objects.create(cart=anonymous, variant=variant, quantity=2)

    merged = merge_carts(anonymous_cart=anonymous, user=user)

    assert merged.lines.get().quantity == 3


def test_infinite_stock_reservation_is_consumed_without_changing_on_hand():
    from commerce.services import consume_reservation, create_reservation

    variant = make_variant(sku="INFINITE-CONSUME", on_hand=0)
    variant.stock_is_infinite = True
    variant.save(update_fields=("stock_is_infinite",))

    reservation = create_reservation(
        variant=variant,
        quantity=50,
        reference="infinite-order",
    )
    consume_reservation(reservation)

    variant.refresh_from_db()
    reservation.refresh_from_db()
    assert reservation.status == "consumed"
    assert reservation.tracks_inventory is False
    assert variant.on_hand == 0


def test_checkout_reservation_enforces_optional_limit_for_infinite_stock():
    from commerce.services import PurchaseLimitExceeded, create_reservation

    variant = make_variant(sku="INFINITE-CHECKOUT-CAP", on_hand=0)
    variant.stock_is_infinite = True
    variant.max_purchase_quantity = 4
    variant.save(update_fields=("stock_is_infinite", "max_purchase_quantity"))

    with pytest.raises(PurchaseLimitExceeded):
        create_reservation(
            variant=variant,
            quantity=5,
            reference="capped-order",
        )


def test_checkout_reports_purchase_limit_changed_after_cart_was_created(
    django_user_model,
):
    from commerce.checkout import CheckoutError, confirm_checkout
    from commerce.models import Cart, CartLine
    from tests.test_checkout_domain import (
        ApprovedSID,
        PreferencePayment,
        make_billing_profile,
        make_customer,
    )

    user = django_user_model.objects.create_user(
        email="checkout-limit@example.test",
        email_verified_at=timezone.now(),
    )
    make_customer(user)
    billing_profile = make_billing_profile(user)
    variant = make_variant(sku="CHECKOUT-LIMIT-CHANGED", on_hand=0)
    variant.stock_is_infinite = True
    variant.max_purchase_quantity = 1
    variant.save(update_fields=("stock_is_infinite", "max_purchase_quantity"))
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=2)

    with pytest.raises(CheckoutError) as error:
        confirm_checkout(
            cart=cart,
            user=user,
            fulfillment_method="pickup",
            sid_adapter=ApprovedSID(),
            payment_adapter=PreferencePayment(),
            billing_profile=billing_profile,
            consent=True,
            idempotency_key="729df5c0-b966-475f-9f7e-073990fd45ee",
        )

    assert error.value.code == "purchase_limit_exceeded"


def test_refund_does_not_create_stock_for_an_infinite_variant(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.payments import apply_payment, refund_order
    from commerce.services import create_reservation
    from tests.test_checkout_domain import (
        RefundAdapter,
        make_transaction,
        pending_order,
        valid_payment,
    )

    user = django_user_model.objects.create_user(email="infinite-refund@example.test")
    variant = make_variant(sku="INFINITE-REFUND", on_hand=0)
    variant.stock_is_infinite = True
    variant.save(update_fields=("stock_is_infinite",))
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=20)
    order = pending_order(cart)
    reservation = create_reservation(
        variant=variant,
        quantity=20,
        reference=str(order.public_id),
    )
    order.reservations.add(reservation)
    payment = make_transaction(order)
    apply_payment(transaction=payment, payment=valid_payment(payment))

    refund = refund_order(
        order=order,
        adapter=RefundAdapter(),
        idempotency_key="dd12d5f0-b9e3-48b1-87b8-8cc62bf7ac71",
    )

    variant.refresh_from_db()
    assert variant.on_hand == 0
    assert refund.stock_restored is False


def test_management_product_saves_stock_mode_and_blank_purchase_limit(
    django_user_model,
):
    from rest_framework.test import APIRequestFactory

    from backoffice.catalog_serializers import ManagementProductSerializer
    from catalog.models import Category

    category = Category.objects.create(name="Ediciones", slug="ediciones")
    owner = django_user_model.objects.create_superuser(
        email="stock-owner@example.test",
        password="StrongPassword!2026",
    )
    request = APIRequestFactory().post("/api/v1/management/products/")
    request.user = owner
    serializer = ManagementProductSerializer(
        data={
            "name": "Agenda perpetua",
            "slug": "agenda-perpetua",
            "category_id": category.pk,
            "variants": [
                {
                    "sku": "AGENDA-INFINITA",
                    "name": "Tapa azul",
                    "price": "15000.00",
                    "cost": "8000.00",
                    "on_hand": 0,
                    "stock_is_infinite": True,
                    "max_purchase_quantity": None,
                    "packaged_weight_grams": 400,
                    "length_cm": "21.00",
                    "width_cm": "15.00",
                    "height_cm": "2.00",
                }
            ],
        },
        context={"request": request},
    )

    assert serializer.is_valid(), serializer.errors
    product = serializer.save()
    payload = ManagementProductSerializer(product).data["variants"][0]
    assert payload["stock_is_infinite"] is True
    assert payload["max_purchase_quantity"] is None


def test_public_product_exposes_infinite_stock_and_optional_purchase_limit(client):
    variant = make_variant(sku="PUBLIC-INFINITE", on_hand=0)
    variant.stock_is_infinite = True
    variant.max_purchase_quantity = 12
    variant.save(update_fields=("stock_is_infinite", "max_purchase_quantity"))

    response = client.get(f"/api/v1/products/{variant.product.slug}/")

    assert response.status_code == 200
    assert response.json()["is_available"] is True
    payload = response.json()["variants"][0]
    assert payload["stock_is_infinite"] is True
    assert payload["purchase_limit"] == 12

    in_stock = client.get("/api/v1/products/?availability=in_stock")
    out_of_stock = client.get("/api/v1/products/?availability=out_of_stock")
    assert [item["id"] for item in in_stock.json()["results"]] == [variant.product_id]
    assert out_of_stock.json()["results"] == []
