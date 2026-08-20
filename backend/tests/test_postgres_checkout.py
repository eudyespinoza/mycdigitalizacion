import threading

import pytest
from django.db import connection
from django.utils import timezone

from tests.test_checkout_domain import make_transaction, pending_order, valid_payment
from tests.test_commerce_domain import make_variant
from tests.test_postgres_round1 import run_concurrently


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_payment_and_expiry_race_never_consumes_released_stock(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine, StockReservation
    from commerce.payments import PaymentMismatch, apply_payment
    from commerce.services import release_reservation

    user = django_user_model.objects.create_user(email="payment-race@example.test")
    variant = make_variant(sku="PAYMENT-RACE", on_hand=1)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = pending_order(cart)
    reservation = StockReservation.objects.create(
        variant=variant,
        quantity=1,
        reference=str(order.public_id),
        expires_at=timezone.now() - timezone.timedelta(seconds=1),
    )
    order.reservations.add(reservation)
    payment_transaction = make_transaction(order)

    def approve():
        try:
            apply_payment(
                transaction=payment_transaction,
                payment=valid_payment(payment_transaction),
            )
        except PaymentMismatch:
            return "needs_attention"
        return "approved"

    outcomes = run_concurrently(approve, lambda: release_reservation(reservation).status)

    reservation.refresh_from_db()
    payment_transaction.refresh_from_db()
    order.refresh_from_db()
    variant.refresh_from_db()
    assert sorted(outcomes) == ["needs_attention", "released"]
    assert reservation.status == StockReservation.Status.RELEASED
    assert payment_transaction.status == "needs_attention"
    assert order.payment_status == "needs_attention"
    assert variant.on_hand == 1


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_checkout_confirmation_reuses_one_order(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.checkout import confirm_checkout
    from commerce.models import Cart, CartLine, Order, PaymentTransaction, StockReservation
    from tests.test_checkout_domain import (
        ApprovedSID,
        PreferencePayment,
        make_billing_profile,
        make_customer,
    )

    user = django_user_model.objects.create_user(
        email="concurrent-checkout@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing_profile = make_billing_profile(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart, variant=make_variant(sku="CONCURRENT-CHECKOUT", on_hand=2), quantity=1
    )
    idempotency_key = "6947e37e-8531-4b25-9628-2e250fa726e1"

    def confirm():
        current_user = django_user_model.objects.get(pk=user.pk)
        return str(
            confirm_checkout(
                cart=Cart.objects.get(pk=cart.pk),
                user=current_user,
                fulfillment_method="pickup",
                sid_adapter=ApprovedSID(),
                payment_adapter=PreferencePayment(),
                billing_profile=type(billing_profile).objects.get(pk=billing_profile.pk),
                consent=True,
                idempotency_key=idempotency_key,
            ).order.public_id
        )

    outcomes = run_concurrently(confirm, confirm)

    assert len(set(outcomes)) == 1
    assert Order.objects.count() == 1
    assert PaymentTransaction.objects.count() == 1
    assert StockReservation.objects.count() == 1


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_shipment_creation_calls_carrier_once(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine, Shipment, ShippingQuote
    from commerce.services import create_pending_identity_order, transition_order_status
    from commerce.shipping import create_order_shipment

    user = django_user_model.objects.create_user(email="concurrent-shipment@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="CONCURRENT-SHIP"), quantity=1)
    quote = ShippingQuote.objects.create(
        user=user,
        service="CP",
        postal_code="1414",
        parcels=[
            {
                "box_code": "one",
                "weight_grams": 1000,
                "length_cm": "10",
                "width_cm": "10",
                "height_cm": "10",
            }
        ],
        base_amount="10.00",
        total_amount="10.00",
        cart_fingerprint="c" * 64,
        expires_at=timezone.now() + timezone.timedelta(minutes=15),
    )
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={
            "street": "Uno",
            "number": "1",
            "postal_code": "1414",
            "locality": "CABA",
            "province_code": "C",
        },
        fiscal_snapshot={},
        fulfillment_method="shipping",
        shipping_quote=quote,
    )
    transition_order_status(order=order, field="identity_status", value="verified")
    transition_order_status(order=order, field="payment_status", value="paid")
    calls = 0
    calls_lock = threading.Lock()

    class Adapter:
        def import_shipment(self, payload, *, idempotency_key):
            del payload, idempotency_key
            nonlocal calls
            with calls_lock:
                calls += 1
            return {"createdAt": "2026-08-19T12:00:00-03:00"}

    adapter = Adapter()

    def create():
        return create_order_shipment(order=type(order).objects.get(pk=order.pk), adapter=adapter).pk

    outcomes = run_concurrently(create, create)

    assert len(set(outcomes)) == 1
    assert Shipment.objects.count() == 1
    assert calls == 1
