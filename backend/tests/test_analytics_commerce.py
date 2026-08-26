import uuid
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import RequestFactory

from analytics.models import (
    AnalyticsConversion,
    AnalyticsOrderAttribution,
    AnalyticsSession,
)


def make_variant(*, sku="ANA-COMMERCE"):
    from catalog.models import Category, Product, ProductVariant
    from catalog.services import activate_product

    category, _ = Category.objects.get_or_create(name="Medición", slug="medicion")
    product = Product.objects.create(
        category=category,
        name=f"Producto {sku}",
        slug=f"producto-{sku.casefold()}",
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku=sku,
        price=Decimal("5000.00"),
        cost=Decimal("2200.00"),
        packaged_weight_grams=400,
        length_cm=Decimal("10"),
        width_cm=Decimal("10"),
        height_cm=Decimal("10"),
        on_hand=10,
    )
    activate_product(product=product)
    return variant


def make_order(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import create_pending_identity_order

    user = django_user_model.objects.create_user(email=f"buyer-{uuid.uuid4()}@example.test")
    variant = make_variant(sku=f"ANA-{uuid.uuid4().hex[:8]}")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )
    return order


def make_transaction(order):
    from commerce.models import PaymentTransaction

    return PaymentTransaction.objects.create(
        order=order,
        amount=order.total_snapshot,
        currency="ARS",
        expected_collector_id="collector",
        live_mode=False,
    )


def approved_payload(payment_transaction):
    return {
        "id": f"approved-{payment_transaction.pk}",
        "status": "approved",
        "external_reference": str(payment_transaction.external_reference),
        "transaction_amount": str(payment_transaction.amount),
        "currency_id": "ARS",
        "collector_id": "collector",
        "live_mode": False,
        "metadata": {"order_id": str(payment_transaction.order.public_id)},
    }


def request_for_session(session):
    from django.core import signing

    from analytics.services import SESSION_SIGNING_SALT

    request = RequestFactory().post("/checkout/")
    request.COOKIES[settings.ANALYTICS_SESSION_COOKIE_NAME] = signing.dumps(
        str(session.public_id),
        salt=SESSION_SIGNING_SALT,
    )
    return request


@pytest.mark.django_db
def test_link_order_to_request_session_is_idempotent(django_user_model):
    from analytics.services import link_order_to_request_session

    session = AnalyticsSession.objects.create(
        visitor_hash="a" * 64,
        entry_path="/catalogo",
    )
    order = make_order(django_user_model)
    request = request_for_session(session)

    first = link_order_to_request_session(request, order)
    second = link_order_to_request_session(request, order)

    assert first.pk == second.pk
    assert AnalyticsOrderAttribution.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_checkout_without_analytics_cookie_does_not_create_attribution(django_user_model):
    from analytics.services import link_order_to_request_session

    order = make_order(django_user_model)

    assert link_order_to_request_session(RequestFactory().post("/checkout/"), order) is None
    assert not AnalyticsOrderAttribution.objects.exists()


@pytest.mark.django_db
def test_paid_payment_creates_one_server_authoritative_conversion(
    django_user_model,
    django_capture_on_commit_callbacks,
):
    from analytics.services import link_order_to_request_session
    from commerce.payments import apply_payment

    session = AnalyticsSession.objects.create(
        visitor_hash="b" * 64,
        entry_path="/producto/medible",
    )
    order = make_order(django_user_model)
    link_order_to_request_session(request_for_session(session), order)
    payment_transaction = make_transaction(order)
    payload = approved_payload(payment_transaction)

    with django_capture_on_commit_callbacks(execute=True):
        apply_payment(transaction=payment_transaction, payment=payload)
    with django_capture_on_commit_callbacks(execute=True):
        apply_payment(transaction=payment_transaction, payment=payload)

    conversion = AnalyticsConversion.objects.get(order=order)
    assert conversion.session == session
    assert conversion.transaction == payment_transaction
    assert conversion.total == order.total_snapshot
    assert AnalyticsConversion.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_analytics_failure_never_blocks_cart(client, monkeypatch):
    variant = make_variant(sku="ANA-FAIL-SAFE")

    def fail(*args, **kwargs):
        raise RuntimeError("analytics unavailable")

    monkeypatch.setattr("api_views.analytics_services.record_cart_addition", fail)
    response = client.post(
        "/api/v1/cart/",
        {"variant_id": variant.pk, "quantity": 1},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["lines"][0]["quantity"] == 1


@pytest.mark.django_db
def test_analytics_callback_failure_never_rolls_back_paid_order(
    django_user_model,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    from commerce.payments import apply_payment

    order = make_order(django_user_model)
    payment_transaction = make_transaction(order)

    def fail(*args, **kwargs):
        raise RuntimeError("analytics unavailable")

    monkeypatch.setattr("analytics.services.record_paid_conversion", fail)
    with django_capture_on_commit_callbacks(execute=True):
        apply_payment(
            transaction=payment_transaction,
            payment=approved_payload(payment_transaction),
        )

    order.refresh_from_db()
    payment_transaction.refresh_from_db()
    assert order.payment_status == order.PaymentStatus.PAID
    assert payment_transaction.approved_at is not None
