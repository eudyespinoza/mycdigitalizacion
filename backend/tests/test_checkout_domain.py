import hashlib
import json
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from tests.test_commerce_domain import make_variant


class ApprovedSID:
    def verify(self, *, dni, consent):
        from commerce.identity import SIDResult

        assert dni == "12345678"
        assert consent is True
        return SIDResult("approved", "sid-ref", {"document_last4": "5678"})


class UnavailableSID:
    def verify(self, *, dni, consent):
        from providers import ProviderUnavailable

        raise ProviderUnavailable("offline", diagnostics="timeout")


@pytest.mark.django_db
def test_sid_unavailable_persists_pending_review_and_manual_approval_requires_staff(
    django_user_model,
):
    from commerce.identity_service import approve_identity_manually, validate_identity

    user = django_user_model.objects.create_user(email="identity@example.test")
    customer = make_customer(user)
    attempt = validate_identity(customer=customer, adapter=UnavailableSID(), consent=True)

    assert attempt.status == "pending_review"
    assert attempt.masked_audit == {"document": "••••5678"}
    assert attempt.staff_diagnostics == "timeout"
    with pytest.raises(PermissionDenied):
        approve_identity_manually(attempt=attempt, actor=user, reason="document checked")
    staff = django_user_model.objects.create_user(email="staff@example.test", is_staff=True)
    with pytest.raises(ValueError, match="reason"):
        approve_identity_manually(attempt=attempt, actor=staff, reason=" ")

    approved = approve_identity_manually(
        attempt=attempt, actor=staff, reason="Documento verificado en revisión"
    )
    assert approved.status == "approved"
    assert approved.reviewed_by == staff


@pytest.mark.django_db
def test_pending_identity_checkout_has_no_payment_or_reservation(django_user_model):
    from commerce.checkout import confirm_checkout
    from commerce.models import Cart, CartLine, PaymentTransaction, StockReservation

    user = django_user_model.objects.create_user(
        email="pending@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="PENDING-ID"), quantity=1)

    result = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=MustNotBeCalled(),
    )

    assert result.order.identity_status == "pending_identity"
    assert result.checkout_url == ""
    assert not PaymentTransaction.objects.exists()
    assert not StockReservation.objects.exists()


@pytest.mark.django_db
def test_confirm_checkout_rechecks_stock_and_creates_twenty_minute_reservation(
    django_user_model,
):
    from commerce.checkout import CheckoutError, confirm_checkout
    from commerce.models import Cart, CartLine

    user = django_user_model.objects.create_user(
        email="approved@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    cart = Cart.objects.create(user=user)
    variant = make_variant(sku="CHECKOUT", price="120.00", on_hand=1)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    payment = PreferencePayment()

    result = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=ApprovedSID(),
        payment_adapter=payment,
    )

    reservation = result.order.reservations.get()
    assert abs(
        reservation.expires_at - (result.transaction.created_at + timezone.timedelta(minutes=20))
    ) < timezone.timedelta(seconds=2)
    assert result.transaction.amount == Decimal("120.00")
    assert result.checkout_url == "https://pay.example.test/preference"

    second_cart = Cart.objects.create(
        user=django_user_model.objects.create_user(
            email="no-stock@example.test", email_verified_at=timezone.now()
        )
    )
    make_customer(second_cart.user)
    CartLine.objects.create(cart=second_cart, variant=variant, quantity=1)
    with pytest.raises(CheckoutError) as error:
        confirm_checkout(
            cart=second_cart,
            user=second_cart.user,
            fulfillment_method="pickup",
            sid_adapter=ApprovedSID(),
            payment_adapter=payment,
        )
    assert error.value.code == "insufficient_stock"


@pytest.mark.django_db
def test_webhook_is_stored_before_validation_and_deduplicated(django_user_model):
    from commerce.models import PaymentWebhookEvent
    from commerce.payments import WebhookRejected, ingest_webhook

    raw = json.dumps({"id": "evt-1", "type": "payment", "data": {"id": "42"}}).encode()
    headers = {"x-request-id": "req-1", "x-signature": "ts=1,v1=bad"}
    with pytest.raises(WebhookRejected):
        ingest_webhook(raw_body=raw, headers=headers, secret="secret", enqueue=lambda pk: None)

    event = PaymentWebhookEvent.objects.get()
    assert event.raw_body_hash == hashlib.sha256(raw).hexdigest()
    assert event.signature_valid is False
    duplicate = ingest_webhook(
        raw_body=raw, headers=headers, secret="secret", enqueue=lambda pk: None
    )
    assert duplicate.duplicate is True
    assert PaymentWebhookEvent.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "wrong"),
    [("transaction_amount", "99.00"), ("currency_id", "USD"), ("collector_id", "other")],
)
def test_payment_mismatches_become_needs_attention(django_user_model, field, wrong):
    from commerce.models import Cart, CartLine
    from commerce.payments import PaymentMismatch, apply_payment

    user = django_user_model.objects.create_user(email=f"{field}@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku=f"PAY-{field}"), quantity=1)
    order = pending_order(cart)
    transaction = make_transaction(order)
    payment = valid_payment(transaction)
    payment[field] = wrong

    with pytest.raises(PaymentMismatch):
        apply_payment(transaction=transaction, payment=payment)

    transaction.refresh_from_db()
    order.refresh_from_db()
    assert transaction.status == "needs_attention"
    assert order.payment_status == "needs_attention"


@pytest.mark.django_db
def test_out_of_order_pending_payment_does_not_downgrade_paid_order(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.payments import apply_payment

    user = django_user_model.objects.create_user(email="out-of-order@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="OUT-OF-ORDER"), quantity=1)
    order = pending_order(cart)
    transaction = make_transaction(order)
    approved = valid_payment(transaction)
    apply_payment(transaction=transaction, payment=approved)
    pending = valid_payment(transaction) | {"status": "pending"}

    apply_payment(transaction=transaction, payment=pending)

    order.refresh_from_db()
    transaction.refresh_from_db()
    assert order.payment_status == "paid"
    assert transaction.status == "approved"


def make_customer(user):
    from accounts.models import CustomerProfile

    customer = CustomerProfile.objects.create(user=user, consent_version="privacy-v1")
    customer.set_dni("12345678")
    customer.save()
    return customer


def pending_order(cart):
    from commerce.services import create_pending_identity_order

    return create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": cart.user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )


def make_transaction(order):
    import uuid

    from commerce.models import PaymentTransaction

    return PaymentTransaction.objects.create(
        order=order,
        external_reference=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        amount=order.total_snapshot,
        currency="ARS",
        expected_collector_id="collector",
        live_mode=False,
    )


def valid_payment(transaction):
    return {
        "id": f"payment-{transaction.pk}",
        "status": "approved",
        "external_reference": str(transaction.external_reference),
        "transaction_amount": str(transaction.amount),
        "currency_id": "ARS",
        "collector_id": "collector",
        "live_mode": False,
    }


class MustNotBeCalled:
    def create_preference(self, **kwargs):
        raise AssertionError("payment preference must not be created")


class PreferencePayment:
    live_mode = False

    def create_preference(self, **kwargs):
        from commerce.mercadopago import CheckoutPreference

        return CheckoutPreference(
            "pref-1",
            "https://pay.example.test/preference",
            kwargs["now"] + timezone.timedelta(minutes=20),
        )


@pytest.mark.django_db
def test_andreani_sync_maps_cp_and_cpa_without_exposing_full_dataset():
    from locations.providers import AndreaniLocalitiesAdapter
    from locations.services import lookup_localities, sync_localities

    adapter = AndreaniLocalitiesAdapter(
        transport=OneResponseTransport(
            200,
            [
                {
                    "id": "loc-1",
                    "codigoPostal": "1414",
                    "codigoPostalArgentino": "C1414ABC",
                    "localidad": "Villa Crespo",
                    "provincia": "Ciudad Autónoma de Buenos Aires",
                },
                {
                    "id": "loc-2",
                    "codigoPostal": "5000",
                    "codigoPostalArgentino": "X5000AAA",
                    "localidad": "Córdoba",
                    "provincia": "Córdoba",
                },
            ],
        )
    )
    assert sync_localities(adapter=adapter) == 2

    by_cp = lookup_localities("1414")
    by_cpa = lookup_localities("c1414abc")
    assert [(row.locality, row.cpa) for row in by_cp] == [("Villa Crespo", "C1414ABC")]
    assert [row.pk for row in by_cpa] == [row.pk for row in by_cp]
    assert len(lookup_localities("1414", limit=1)) == 1


@pytest.mark.django_db
def test_refund_restores_stock_before_fulfillment_but_requires_return_after_shipment(
    django_user_model,
):
    from commerce.models import Cart, CartLine, Refund
    from commerce.payments import apply_payment, refund_order
    from commerce.services import create_reservation, transition_order_status

    user = django_user_model.objects.create_user(email="refund@example.test")
    variant = make_variant(sku="REFUND", on_hand=2)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = pending_order(cart)
    reservation = create_reservation(variant=variant, quantity=1, reference=str(order.public_id))
    order.reservations.add(reservation)
    payment = make_transaction(order)
    apply_payment(transaction=payment, payment=valid_payment(payment))
    variant.refresh_from_db()
    assert variant.on_hand == 1

    first = refund_order(
        order=order,
        adapter=RefundAdapter(),
        idempotency_key="1f773dd4-aacd-4599-b2aa-bc11977749fb",
    )
    variant.refresh_from_db()
    assert first.stock_restored is True
    assert variant.on_hand == 2
    assert Refund.objects.count() == 1
    assert (
        refund_order(
            order=order,
            adapter=RefundAdapter(),
            idempotency_key="1f773dd4-aacd-4599-b2aa-bc11977749fb",
        ).pk
        == first.pk
    )

    second_variant = make_variant(sku="RETURN", on_hand=2)
    second_cart = Cart.objects.create(
        user=django_user_model.objects.create_user(email="return@example.test")
    )
    CartLine.objects.create(cart=second_cart, variant=second_variant, quantity=1)
    shipped = pending_order(second_cart)
    shipped_reservation = create_reservation(
        variant=second_variant, quantity=1, reference=str(shipped.public_id)
    )
    shipped.reservations.add(shipped_reservation)
    shipped_payment = make_transaction(shipped)
    apply_payment(transaction=shipped_payment, payment=valid_payment(shipped_payment))
    transition_order_status(order=shipped, field="fulfillment_status", value="shipped")
    refund = refund_order(
        order=shipped,
        adapter=RefundAdapter(),
        idempotency_key="cc0a972f-47f3-46ca-9cd8-c449e6bc8e9e",
    )
    second_variant.refresh_from_db()
    assert refund.return_required is True
    assert refund.stock_restored is False
    assert second_variant.on_hand == 1


class OneResponseTransport:
    def __init__(self, status, response):
        self.status = status
        self.response = response

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        return self.status, self.response


class RefundAdapter:
    def refund(self, payment_id, *, amount, idempotency_key):
        return {"id": f"refund-{payment_id}", "status": "approved"}
