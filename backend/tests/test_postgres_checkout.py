import threading
import uuid

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


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_refund_key_across_orders_has_stable_conflict_and_one_provider_call(
    django_user_model,
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine, Refund
    from commerce.payments import RefundError, refund_order

    orders = []
    for index in range(2):
        user = django_user_model.objects.create_user(email=f"refund-race-{index}@example.test")
        cart = Cart.objects.create(user=user)
        CartLine.objects.create(
            cart=cart,
            variant=make_variant(sku=f"REFUND-RACE-{index}"),
            quantity=1,
        )
        order = pending_order(cart)
        payment = make_transaction(order)
        payment.payment_id = f"payment-refund-race-{index}"
        payment.status = payment.Status.APPROVED
        payment.save(update_fields=("payment_id", "status", "updated_at"))
        orders.append(order)

    key = uuid.UUID("7946e717-8748-4e65-bb9a-38f983da4c04")
    calls = 0
    calls_lock = threading.Lock()

    class Adapter:
        def refund(self, payment_id, *, amount=None, idempotency_key):
            del payment_id, amount
            assert idempotency_key == str(key)
            nonlocal calls
            with calls_lock:
                calls += 1
            return {"id": "refund-race", "status": "approved"}

    adapter = Adapter()

    def refund(index):
        try:
            return refund_order(
                order=type(orders[index]).objects.get(pk=orders[index].pk),
                adapter=adapter,
                idempotency_key=key,
            ).status
        except RefundError as exc:
            return exc.code

    outcomes = run_concurrently(lambda: refund(0), lambda: refund(1))

    assert sorted(outcomes) == ["approved", "refund_idempotency_conflict"]
    assert Refund.objects.filter(idempotency_key=key).count() == 1
    assert calls == 1


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_postgresql_multi_parcel_recovery_skips_committed_import(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import ShipmentParcelImport
    from commerce.shipping import create_order_shipment
    from providers import ProviderUnavailable
    from tests.test_task3_round2_regressions import eligible_shipping_order

    order = eligible_shipping_order(django_user_model)

    class Adapter:
        customer_id = "customer"

        def __init__(self):
            self.calls = []
            self.failed = False

        def import_shipment(self, payload, *, idempotency_key):
            self.calls.append((payload["extOrderId"], idempotency_key))
            if payload["extOrderId"].endswith("-2") and not self.failed:
                self.failed = True
                raise ProviderUnavailable("injected parcel failure")
            return {"createdAt": "2026-08-20T12:00:00-03:00"}

    adapter = Adapter()
    with pytest.raises(ProviderUnavailable):
        create_order_shipment(order=order, adapter=adapter)
    assert list(
        ShipmentParcelImport.objects.filter(shipment__order=order).values_list(
            "status", flat=True
        )
    ) == ["imported", "pending"]

    shipment = create_order_shipment(order=order, adapter=adapter)
    assert shipment.status == "imported"
    assert [call[0] for call in adapter.calls].count(f"{order.public_id}-1") == 1
