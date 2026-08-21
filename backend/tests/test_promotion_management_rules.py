from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from catalog.models import Category, Product
from commerce.models import Coupon, PromotionRule
from tests.test_backoffice_content import management_client
from tests.test_commerce_domain import make_variant
from tests.test_postgres_round1 import run_concurrently

pytestmark = pytest.mark.django_db


def offer_payload(*, now, name, product_ids=None, category_ids=None, enabled=True):
    return {
        "name": name,
        "discount_type": "percentage",
        "value": "15.00",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "enabled": enabled,
        "product_ids": product_ids or [],
        "category_ids": category_ids or [],
    }


def coupon_payload(*, now, code, maximum):
    return {
        "code": code,
        "discount_type": "percentage",
        "value": "10.00",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "enabled": True,
        "combinable": False,
        "max_redemptions": maximum,
    }


def test_management_creates_multiple_coupons_and_exposes_effective_usage_limit(
    django_user_model,
):
    client, _ = management_client(django_user_model)
    now = timezone.now()

    first = client.post(
        "/api/v1/management/promotions/coupons/",
        coupon_payload(now=now, code="PRIMERA10", maximum=25),
        format="json",
    )
    second = client.post(
        "/api/v1/management/promotions/coupons/",
        coupon_payload(now=now, code="SEGUNDA10", maximum=None),
        format="json",
    )
    listed = client.get("/api/v1/management/promotions/coupons/")

    assert first.status_code == 201
    assert first.json()["max_redemptions"] == 25
    assert first.json()["used_redemptions"] == 0
    assert first.json()["reserved_redemptions"] == 0
    assert second.status_code == 201
    assert second.json()["max_redemptions"] is None
    assert Coupon.objects.count() == 2
    assert len(listed.json()["results"]) == 2


def test_management_rejects_an_overlapping_offer_for_the_same_product(
    django_user_model,
):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Cuadernos", slug="cuadernos-oferta")
    product = Product.objects.create(
        name="Cuaderno rayado",
        slug="cuaderno-rayado-oferta",
        category=category,
    )
    now = timezone.now()

    first = client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(now=now, name="Oferta uno", product_ids=[product.pk]),
        format="json",
    )
    conflicting = client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(now=now, name="Oferta dos", product_ids=[product.pk]),
        format="json",
    )

    assert first.status_code == 201
    assert conflicting.status_code == 400
    assert conflicting.json()["code"] == "offer_scope_conflict"
    assert PromotionRule.objects.count() == 1


def test_management_rejects_a_category_offer_covering_an_already_offered_product(
    django_user_model,
):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Escritura", slug="escritura-oferta")
    product = Product.objects.create(
        name="Lapicera azul",
        slug="lapicera-azul-oferta",
        category=category,
    )
    now = timezone.now()
    client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(now=now, name="Producto directo", product_ids=[product.pk]),
        format="json",
    )

    conflicting = client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(now=now, name="Categoría completa", category_ids=[category.pk]),
        format="json",
    )

    assert conflicting.status_code == 400
    assert conflicting.json()["code"] == "offer_scope_conflict"


def test_management_allows_non_overlapping_or_paused_offers(django_user_model):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Papel", slug="papel-oferta")
    product = Product.objects.create(
        name="Resma A4",
        slug="resma-a4-oferta",
        category=category,
    )
    now = timezone.now()
    first = client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(now=now, name="Oferta vigente", product_ids=[product.pk]),
        format="json",
    )
    later_payload = offer_payload(
        now=now + timedelta(days=8),
        name="Oferta siguiente",
        product_ids=[product.pk],
    )
    later = client.post(
        "/api/v1/management/promotions/rules/",
        later_payload,
        format="json",
    )
    paused = client.post(
        "/api/v1/management/promotions/rules/",
        offer_payload(
            now=now,
            name="Oferta pausada",
            product_ids=[product.pk],
            enabled=False,
        ),
        format="json",
    )

    assert [first.status_code, later.status_code, paused.status_code] == [201, 201, 201]


def test_offer_boundaries_cannot_share_the_same_active_instant(django_user_model):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Límite", slug="limite-oferta")
    product = Product.objects.create(
        name="Producto límite",
        slug="producto-limite-oferta",
        category=category,
    )
    now = timezone.now()
    boundary = now + timedelta(days=7)
    first_payload = offer_payload(
        now=now,
        name="Oferta hasta el límite",
        product_ids=[product.pk],
    )
    second_payload = offer_payload(
        now=boundary,
        name="Oferta desde el límite",
        product_ids=[product.pk],
    )

    first = client.post(
        "/api/v1/management/promotions/rules/",
        first_payload,
        format="json",
    )
    touching = client.post(
        "/api/v1/management/promotions/rules/",
        second_payload,
        format="json",
    )

    assert first.status_code == 201
    assert touching.status_code == 400
    assert touching.json()["code"] == "offer_scope_conflict"


def test_management_product_list_identifies_the_active_offer(django_user_model):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Agenda", slug="agenda-oferta")
    product = Product.objects.create(
        name="Agenda diaria",
        slug="agenda-diaria-oferta",
        category=category,
    )
    now = timezone.now()
    rule = PromotionRule.objects.create(
        name="Semana de agendas",
        discount_type="percentage",
        value="20.00",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        enabled=True,
    )
    rule.products.add(product)

    response = client.get("/api/v1/management/products/")

    assert response.status_code == 200
    listed = response.json()["results"][0]
    assert listed["on_offer"] is True
    assert listed["active_offer_names"] == ["Semana de agendas"]


def test_promotion_scope_options_returns_every_existing_product_and_category(
    django_user_model,
):
    client, _ = management_client(django_user_model)
    category = Category.objects.create(name="Catálogo completo", slug="catalogo-completo")
    Product.objects.bulk_create(
        [
            Product(
                name=f"Producto {index:03d}",
                slug=f"producto-scope-{index:03d}",
                category=category,
            )
            for index in range(105)
        ]
    )

    response = client.get("/api/v1/management/promotions/scope-options/")

    assert response.status_code == 200
    assert len(response.json()["products"]) == 105
    assert response.json()["products"][0] == {
        "id": Product.objects.order_by("name").first().pk,
        "label": "Producto 000",
        "description": "Catálogo completo",
    }
    assert response.json()["categories"] == [
        {"id": category.pk, "label": "Catálogo completo"}
    ]


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_overlapping_offer_creation_accepts_only_one():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from backoffice.content_serializers import (
        ManagementPromotionRuleSerializer,
        OfferScopeConflict,
    )

    category = Category.objects.create(name="Concurrente", slug="oferta-concurrente")
    product = Product.objects.create(
        name="Producto concurrente",
        slug="producto-oferta-concurrente",
        category=category,
    )
    now = timezone.now()

    def create(name):
        serializer = ManagementPromotionRuleSerializer(
            data=offer_payload(now=now, name=name, product_ids=[product.pk])
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save().pk

    outcomes = run_concurrently(
        lambda: create("Oferta concurrente A"),
        lambda: create("Oferta concurrente B"),
    )

    assert PromotionRule.objects.count() == 1
    assert sum(isinstance(outcome, int) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, OfferScopeConflict) for outcome in outcomes) == 1


def test_coupon_limit_reserves_checkout_consumes_payment_and_releases_refund(
    django_user_model,
):
    from commerce.models import Cart, CartLine
    from commerce.payments import apply_payment, refund_order
    from commerce.services import create_pending_identity_order
    from tests.test_checkout_domain import (
        RefundAdapter,
        make_transaction,
        valid_payment,
    )

    now = timezone.now()
    coupon = Coupon.objects.create(
        code="UNSOLOUSO",
        discount_type="percentage",
        value="10.00",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        max_redemptions=1,
    )
    variant = make_variant(sku="COUPON-CAP", on_hand=10)

    def checkout_cart(email):
        user = django_user_model.objects.create_user(email=email)
        cart = Cart.objects.create(user=user, coupon=coupon)
        CartLine.objects.create(cart=cart, variant=variant, quantity=1)
        return cart

    first_cart = checkout_cart("coupon-first@example.test")
    first_order = create_pending_identity_order(
        cart=first_cart,
        customer_snapshot={"email": first_cart.user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )
    second_cart = checkout_cart("coupon-second@example.test")

    with pytest.raises(ValidationError, match="cupo"):
        create_pending_identity_order(
            cart=second_cart,
            customer_snapshot={"email": second_cart.user.email},
            address_snapshot={},
            fiscal_snapshot={},
            fulfillment_method="pickup",
        )

    redemption = coupon.redemptions.get(order=first_order)
    assert redemption.status == "reserved"
    payment = make_transaction(first_order)
    apply_payment(transaction=payment, payment=valid_payment(payment))
    redemption.refresh_from_db()
    assert redemption.status == "consumed"

    refund_order(
        order=first_order,
        adapter=RefundAdapter(),
        idempotency_key="f7217b61-844f-467d-a690-5fc6780c2c31",
    )
    redemption.refresh_from_db()
    assert redemption.status == "released"

    second_order = create_pending_identity_order(
        cart=second_cart,
        customer_snapshot={"email": second_cart.user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )
    assert second_order.coupon_code_snapshot == coupon.code


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_checkout_cannot_exceed_the_coupon_limit(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine, Order
    from commerce.services import create_pending_identity_order

    now = timezone.now()
    coupon = Coupon.objects.create(
        code="CONCURRENTE1",
        discount_type="fixed",
        value="1.00",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        max_redemptions=1,
    )
    variant = make_variant(sku="COUPON-CONCURRENT", on_hand=10)
    carts = []
    for index in range(2):
        user = django_user_model.objects.create_user(
            email=f"coupon-concurrent-{index}@example.test"
        )
        cart = Cart.objects.create(user=user, coupon=coupon)
        CartLine.objects.create(cart=cart, variant=variant, quantity=1)
        carts.append(cart)

    def checkout(cart):
        return create_pending_identity_order(
            cart=cart,
            customer_snapshot={"email": cart.user.email},
            address_snapshot={},
            fiscal_snapshot={},
            fulfillment_method="pickup",
        )

    outcomes = run_concurrently(
        lambda: checkout(carts[0]),
        lambda: checkout(carts[1]),
    )

    assert Order.objects.count() == 1
    assert sum(isinstance(outcome, Order) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, ValidationError) for outcome in outcomes) == 1
