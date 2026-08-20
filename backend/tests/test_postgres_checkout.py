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
