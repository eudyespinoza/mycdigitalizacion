import threading

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from tests.test_commerce_domain import make_variant


def run_concurrently(*functions):
    barrier = threading.Barrier(len(functions))
    outcomes = []

    def run(function):
        close_old_connections()
        barrier.wait()
        try:
            outcomes.append(function())
        except Exception as exc:  # surfaced by the assertions, not swallowed
            outcomes.append(exc)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=run, args=(function,)) for function in functions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive(), "concurrent database operation deadlocked"
    return outcomes


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_email_verification_consumes_challenge_once(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from accounts.models import EmailVerificationChallenge
    from accounts.services import consume_email_verification_challenge

    user = django_user_model.objects.create_user(email="concurrent-verify@example.test")
    challenge = EmailVerificationChallenge.issue(user=user, code="123456")

    outcomes = run_concurrently(
        *(
            lambda: bool(
                consume_email_verification_challenge(email=user.email, code="123456")
            )
            for _ in range(2)
        )
    )

    challenge.refresh_from_db()
    user.refresh_from_db()
    assert sorted(outcomes) == [False, True]
    assert challenge.consumed_at is not None
    assert user.email_verified_at is not None


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_failed_verification_attempts_are_not_lost(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from accounts.models import EmailVerificationChallenge
    from accounts.services import consume_email_verification_challenge

    user = django_user_model.objects.create_user(email="concurrent-attempts@example.test")
    challenge = EmailVerificationChallenge.issue(user=user, code="123456")

    outcomes = run_concurrently(
        *(
            lambda: consume_email_verification_challenge(email=user.email, code="000000")
            for _ in range(2)
        )
    )

    challenge.refresh_from_db()
    assert outcomes == [None, None]
    assert challenge.attempt_count == 2


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_authenticated_cart_creation_and_line_adds_are_lossless(
    django_user_model,
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart
    from commerce.services import add_cart_line, get_or_create_user_cart

    user = django_user_model.objects.create_user(email="concurrent-cart@example.test")
    carts = run_concurrently(
        *(lambda: get_or_create_user_cart(user=user).pk for _ in range(2))
    )
    assert len(set(carts)) == 1
    assert Cart.objects.filter(user=user).count() == 1

    cart = Cart.objects.get(user=user)
    variant = make_variant(sku="CONCURRENT-CART")
    outcomes = run_concurrently(
        lambda: add_cart_line(cart=cart, variant=variant, quantity=2).quantity,
        lambda: add_cart_line(cart=cart, variant=variant, quantity=3).quantity,
    )

    assert not any(isinstance(outcome, Exception) for outcome in outcomes), outcomes
    assert cart.lines.get(variant=variant).quantity == 5


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_anonymous_cart_merges_are_lossless(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine
    from commerce.services import merge_carts

    user = django_user_model.objects.create_user(email="concurrent-merge@example.test")
    variant = make_variant(sku="CONCURRENT-MERGE")
    first = Cart.objects.create()
    second = Cart.objects.create()
    CartLine.objects.create(cart=first, variant=variant, quantity=2)
    CartLine.objects.create(cart=second, variant=variant, quantity=3)

    outcomes = run_concurrently(
        lambda: merge_carts(anonymous_cart=first, user=user).pk,
        lambda: merge_carts(anonymous_cart=second, user=user).pk,
    )

    assert not any(isinstance(outcome, Exception) for outcome in outcomes), outcomes
    assert len(set(outcomes)) == 1
    destination = Cart.objects.get(user=user)
    assert destination.lines.get(variant=variant).quantity == 5
    assert not Cart.objects.filter(pk__in=(first.pk, second.pk)).exists()


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_cart_mutation_and_order_snapshot_remain_reconciled(django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import Cart, CartLine
    from commerce.services import add_cart_line, create_pending_identity_order

    user = django_user_model.objects.create_user(email="snapshot-race@example.test")
    variant = make_variant(sku="SNAPSHOT-RACE", price="10.00")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)

    def create_order():
        order = create_pending_identity_order(
            cart=cart,
            customer_snapshot={"email": user.email},
            address_snapshot={},
            fiscal_snapshot={},
            fulfillment_method="pickup",
        )
        item = order.items.get()
        return item.quantity, item.line_total_snapshot, order.total_snapshot

    outcomes = run_concurrently(
        create_order,
        lambda: add_cart_line(cart=cart, variant=variant, quantity=1).quantity,
    )

    assert not any(isinstance(outcome, Exception) for outcome in outcomes), outcomes
    snapshot = next(outcome for outcome in outcomes if isinstance(outcome, tuple))
    quantity, item_total, order_total = snapshot
    assert quantity in (1, 2)
    assert item_total == order_total == variant.price * quantity


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_expired_reservation_cannot_consume_stock_reused_by_a_live_reservation():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import StockReservation
    from commerce.services import consume_reservation, create_reservation

    variant = make_variant(sku="PG-EXPIRED", on_hand=5)
    expired = StockReservation.objects.create(
        variant=variant,
        quantity=5,
        reference="synthetic-expired",
        expires_at=timezone.now() - timezone.timedelta(seconds=1),
    )
    live = create_reservation(variant=variant, quantity=5, reference="synthetic-live")

    consume_reservation(expired)

    variant.refresh_from_db()
    expired.refresh_from_db()
    assert expired.status == StockReservation.Status.RELEASED
    assert live.status == StockReservation.Status.ACTIVE
    assert variant.on_hand == 5
