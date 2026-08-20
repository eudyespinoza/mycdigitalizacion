import uuid
from threading import Lock

import pytest
from django.conf import settings
from django.core.cache.backends.redis import RedisCache
from django.db import connection

from tests.test_commerce_domain import make_variant
from tests.test_commerce_round1 import pending_order
from tests.test_postgres_round1 import run_concurrently


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_admin_login_throttle_is_atomic_across_real_redis_clients():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL/Redis integration test")

    from config.admin_security import AdminLoginThrottle

    first = AdminLoginThrottle(
        RedisCache(settings.CELERY_BROKER_URL, {}), maximum=3, timeout=60
    )
    second = AdminLoginThrottle(
        RedisCache(settings.CELERY_BROKER_URL, {}), maximum=3, timeout=60
    )
    key = f"task5a-real-redis-{uuid.uuid4()}"
    try:
        assert sorted(
            run_concurrently(
                lambda: first.reserve(key),
                lambda: second.reserve(key),
                lambda: first.reserve(key),
            )
        ) == [1, 2, 3]
        assert first.is_blocked(key) and second.is_blocked(key)
    finally:
        first.clear(key)


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_order_cancellation_is_single_transition_and_single_audit(
    django_user_model,
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.cancellation import cancel_order
    from commerce.models import Cart, CartLine, OrderAuditEvent

    customer = django_user_model.objects.create_user(email="concurrent-cancel@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(
        cart=cart, variant=make_variant(sku="CONCURRENT-CANCEL"), quantity=1
    )
    order = pending_order(cart)
    actor = django_user_model.objects.create_user(
        email="concurrent-cancel-actor@example.test", is_staff=True
    )

    outcomes = run_concurrently(
        lambda: cancel_order(order=order, actor=actor, reason="Concurrente").fulfillment_status,
        lambda: cancel_order(order=order, actor=actor, reason="Concurrente").fulfillment_status,
    )

    assert outcomes == ["cancelled", "cancelled"]
    assert OrderAuditEvent.objects.filter(order=order, kind="admin_cancelled").count() == 1


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_admin_refund_retries_share_provider_operation_and_audit(
    django_user_model,
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.admin_services import perform_order_admin_action
    from commerce.models import Cart, CartLine, Order, OrderAuditEvent, PaymentTransaction, Refund
    from tests.test_checkout_domain import make_transaction

    customer = django_user_model.objects.create_user(email="concurrent-refund@example.test")
    cart = Cart.objects.create(user=customer)
    CartLine.objects.create(
        cart=cart, variant=make_variant(sku="CONCURRENT-REFUND"), quantity=1
    )
    order = pending_order(cart)
    payment = make_transaction(order)
    payment.payment_id = "payment-concurrent-refund"
    payment.status = PaymentTransaction.Status.APPROVED
    payment.save(update_fields=("payment_id", "status", "updated_at"))
    operator = django_user_model.objects.create_superuser(
        email="concurrent-refund-operator@example.test"
    )
    provider_calls = 0
    provider_lock = Lock()

    class Adapter:
        def refund(self, payment_id, *, amount, idempotency_key):
            del payment_id, amount, idempotency_key
            nonlocal provider_calls
            with provider_lock:
                provider_calls += 1
            return {"id": "provider-refund-concurrent", "status": "approved"}

    adapter = Adapter()

    def refund_once():
        perform_order_admin_action(
            action="refund",
            order=Order.objects.get(pk=order.pk),
            actor=operator,
            reason="Retry concurrente",
            adapters={"payment": adapter},
        )
        return Refund.objects.get(order=order).provider_refund_id

    outcomes = run_concurrently(refund_once, refund_once)

    assert outcomes == ["provider-refund-concurrent", "provider-refund-concurrent"]
    assert provider_calls == 1
    assert Refund.objects.filter(order=order).count() == 1
    assert OrderAuditEvent.objects.filter(
        order=order, kind="admin_refund_completed"
    ).count() == 1
