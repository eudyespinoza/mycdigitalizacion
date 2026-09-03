import base64
import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import override_settings
from django.utils import timezone

from tests.test_checkout_domain import (
    ApprovedSID,
    PreferencePayment,
    UnavailableSID,
    make_customer,
    make_transaction,
    pending_order,
    valid_payment,
)
from tests.test_commerce_domain import make_variant


class ContractTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "json": json,
                "params": params,
                "timeout": timeout,
            }
        )
        return next(self.responses)


def make_billing_profile(user, *, label="Consumidor final"):
    from accounts.models import BillingProfile

    profile = BillingProfile.objects.create(
        customer=user.customer_profile,
        label=label,
        legal_name="Ada Compradora",
        tax_condition="consumidor_final",
    )
    profile.set_cuit("20-12345678-6")
    profile.save()
    return profile


def make_checkout_cart(django_user_model, *, email="checkout-round1@example.test", sku="R1"):
    from commerce.models import Cart, CartLine

    user = django_user_model.objects.create_user(email=email, email_verified_at=timezone.now())
    make_customer(user)
    profile = make_billing_profile(user)
    cart = Cart.objects.create(user=user)
    variant = make_variant(sku=sku, price="120.00", on_hand=5)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    return user, profile, cart, variant


def test_micorreo_v1_uses_basic_token_and_documented_rate_contract():
    from commerce.shipping import CorreoArgentinoAdapter, ShippingPolicy

    transport = ContractTransport(
        [
            (200, {"token": "jwt-token", "expires": "2030-01-01 00:00:00"}),
            (
                200,
                {
                    "customerId": "0000550997",
                    "validTo": "2030-01-01T00:00:00-03:00",
                    "rates": [
                        {
                            "deliveredType": "D",
                            "productType": "CP",
                            "productName": "Correo Argentino Clasico",
                            "price": 498.06,
                            "deliveryTimeMin": "2",
                            "deliveryTimeMax": "5",
                        }
                    ],
                },
            ),
        ]
    )
    adapter = CorreoArgentinoAdapter(
        base_url="https://apitest.correoargentino.com.ar/micorreo/v1",
        username="api-user",
        password="api-password",
        customer_id="0000550997",
        origin_postal_code="1757",
        transport=transport,
    )

    quote = adapter.quote(
        postal_code="1704",
        parcels=[
            {
                "weight_grams": 2500,
                "height_cm": "10",
                "width_cm": "20",
                "length_cm": "30",
            }
        ],
        policy=ShippingPolicy(),
    )

    token_call, rate_call = transport.calls
    assert token_call["url"].endswith("/token")
    assert token_call["json"] is None
    assert (
        token_call["headers"]["Authorization"]
        == "Basic " + base64.b64encode(b"api-user:api-password").decode()
    )
    assert rate_call["url"].endswith("/rates")
    assert rate_call["json"] == {
        "customerId": "0000550997",
        "postalCodeOrigin": "1757",
        "postalCodeDestination": "1704",
        "deliveredType": "D",
        "dimensions": {"weight": 2500, "height": 10, "width": 20, "length": 30},
    }
    assert quote.base_amount == Decimal("498.06")
    assert quote.service == "CP"


def test_micorreo_import_tracking_and_unsupported_label_follow_public_contract():
    from commerce.shipping import CorreoArgentinoAdapter
    from providers import ProviderNotSupported

    transport = ContractTransport(
        [
            (200, {"token": "jwt-token"}),
            (200, {"createdAt": "2026-08-19T12:00:00-03:00"}),
            (
                200,
                [
                    {
                        "id": "000017496",
                        "productId": "HC",
                        "trackingNumber": "TRACK-1",
                        "events": [{"event": "PREIMPOSICION", "date": "19-08-2026 12:00"}],
                    }
                ],
            ),
        ]
    )
    adapter = CorreoArgentinoAdapter(
        base_url="https://apitest.correoargentino.com.ar/micorreo/v1",
        username="u",
        password="p",
        customer_id="customer-1",
        origin_postal_code="1757",
        transport=transport,
    )
    payload = {
        "customerId": "customer-1",
        "extOrderId": "order-1",
        "orderNumber": "order-1",
        "recipient": {"name": "Ada", "email": "ada@example.test"},
        "shipping": {
            "deliveryType": "D",
            "productType": "CP",
            "address": {"postalCode": "1704"},
            "weight": 1000,
            "declaredValue": 500,
            "height": 20,
            "length": 40,
            "width": 20,
        },
    }

    assert adapter.import_shipment(payload, idempotency_key="idem") == {
        "createdAt": "2026-08-19T12:00:00-03:00"
    }
    tracking = adapter.tracking("TRACK-1")

    assert transport.calls[1]["url"].endswith("/shipping/import")
    assert transport.calls[1]["json"] == payload
    assert transport.calls[2]["url"].endswith("/shipping/tracking")
    assert transport.calls[2]["json"] == {"shippingId": "TRACK-1"}
    assert tracking[0]["events"][0]["event"] == "PREIMPOSICION"
    with pytest.raises(ProviderNotSupported):
        adapter.label("TRACK-1")


def test_equal_volume_packing_is_order_independent_and_emits_box_dimensions():
    from commerce.packing import Box, PackItem, pack_items

    box1 = Box("b1", Decimal("3"), Decimal("3"), Decimal("3"), 100, 5000)
    box2 = Box("b2", Decimal("6"), Decimal("4"), Decimal("3"), 100, 5000)
    units = [
        PackItem("A", Decimal("1"), Decimal("2"), Decimal("6"), 100, 1),
        PackItem("B", Decimal("1"), Decimal("3"), Decimal("4"), 100, 1),
        PackItem("C", Decimal("2"), Decimal("2"), Decimal("3"), 100, 1),
    ]

    first = pack_items(units, [box1, box2])
    second = pack_items(list(reversed(units)), [box1, box2])

    assert first == second
    assert [parcel.box_code for parcel in first.parcels] == ["b2"]
    assert first.parcels[0].length_cm == Decimal("6")
    assert first.parcels[0].width_cm == Decimal("4")
    assert first.parcels[0].height_cm == Decimal("3")


@pytest.mark.django_db
def test_quote_fingerprint_changes_with_price_coupon_address_and_package(django_user_model):
    from commerce.checkout import cart_fingerprint
    from commerce.models import Cart, CartLine, Coupon
    from locations.models import Address

    user = django_user_model.objects.create_user(email="fingerprint@example.test")
    cart = Cart.objects.create(user=user)
    variant = make_variant(sku="FINGERPRINT", price="100.00")
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    address = Address.objects.create(
        user=user,
        label="Casa",
        street="Uno",
        number="1",
        postal_code="1414",
        locality="CABA",
        province="CABA",
        needs_review=False,
    )
    parcels = [
        {
            "box_code": "one",
            "weight_grams": 1000,
            "length_cm": "10",
            "width_cm": "10",
            "height_cm": "10",
        }
    ]
    first = cart_fingerprint(cart, address=address, parcels=parcels)

    variant.price = Decimal("1.00")
    variant.save(update_fields=("price",))
    assert cart_fingerprint(cart, address=address, parcels=parcels) != first
    variant.price = Decimal("100.00")
    variant.save(update_fields=("price",))

    coupon = Coupon.objects.create(
        code="SAVE",
        discount_type="fixed",
        value=Decimal("5"),
        starts_at=timezone.now() - timezone.timedelta(days=1),
        ends_at=timezone.now() + timezone.timedelta(days=1),
    )
    cart.coupon = coupon
    cart.save(update_fields=("coupon",))
    assert cart_fingerprint(cart, address=address, parcels=parcels) != first
    cart.coupon = None
    cart.save(update_fields=("coupon",))

    address.number = "2"
    address.save(update_fields=("number",))
    assert cart_fingerprint(cart, address=address, parcels=parcels) != first
    address.number = "1"
    address.save(update_fields=("number",))

    changed_parcels = [{**parcels[0], "length_cm": "11"}]
    assert cart_fingerprint(cart, address=address, parcels=changed_parcels) != first


@pytest.mark.django_db
def test_confirm_is_idempotent_and_resume_reuses_bound_pending_order(django_user_model):
    from commerce.checkout import confirm_checkout, resume_checkout
    from commerce.identity_service import approve_identity_manually
    from commerce.models import Order, PaymentTransaction, StockReservation

    user, profile, cart, _variant = make_checkout_cart(django_user_model)
    key = uuid.UUID("1a832381-a646-4f9d-91af-a2feae90684f")
    pending = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=PreferencePayment(),
        billing_profile=profile,
        consent=True,
        idempotency_key=key,
    )
    duplicate = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=ApprovedSID(),
        payment_adapter=PreferencePayment(),
        billing_profile=profile,
        consent=True,
        idempotency_key=key,
    )

    assert duplicate.order.pk == pending.order.pk
    assert Order.objects.count() == 1
    attempt = pending.order.identity_verifications.get()
    staff = django_user_model.objects.create_user(email="reviewer@example.test", is_staff=True)
    approve_identity_manually(attempt=attempt, actor=staff, reason="Documento verificado")
    resumed = resume_checkout(
        order=pending.order, cart=cart, user=user, payment_adapter=PreferencePayment()
    )

    assert resumed.order.pk == pending.order.pk
    assert Order.objects.count() == 1
    assert PaymentTransaction.objects.count() == 1
    assert StockReservation.objects.count() == 1


@pytest.mark.django_db
def test_checkout_requires_affirmative_consent_and_owned_fiscal_profile(django_user_model):
    from commerce.checkout import CheckoutError, confirm_checkout
    from commerce.models import IdentityVerification

    user, profile, cart, _variant = make_checkout_cart(
        django_user_model, email="consent-owner@example.test", sku="CONSENT"
    )
    other, other_profile, _other_cart, _ = make_checkout_cart(
        django_user_model, email="other-profile@example.test", sku="OTHER-PROFILE"
    )
    del other

    with pytest.raises(CheckoutError) as consent_error:
        confirm_checkout(
            cart=cart,
            user=user,
            fulfillment_method="pickup",
            sid_adapter=ApprovedSID(),
            payment_adapter=PreferencePayment(),
            billing_profile=profile,
            consent=False,
            idempotency_key=uuid.uuid4(),
        )
    assert consent_error.value.code == "identity_consent_required"
    assert not IdentityVerification.objects.filter(user=user).exists()

    with pytest.raises(CheckoutError) as profile_error:
        confirm_checkout(
            cart=cart,
            user=user,
            fulfillment_method="pickup",
            sid_adapter=ApprovedSID(),
            payment_adapter=PreferencePayment(),
            billing_profile=other_profile,
            consent=True,
            idempotency_key=uuid.uuid4(),
        )
    assert profile_error.value.code == "billing_profile_invalid"


@pytest.mark.django_db
def test_checkout_snapshots_owned_fiscal_profile_and_binds_identity_attempt(django_user_model):
    from commerce.checkout import confirm_checkout

    user, profile, cart, _variant = make_checkout_cart(
        django_user_model, email="fiscal@example.test", sku="FISCAL"
    )
    result = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=PreferencePayment(),
        billing_profile=profile,
        consent=True,
        idempotency_key=uuid.uuid4(),
    )

    assert result.order.fiscal_snapshot == {
        "profile_id": profile.pk,
        "label": "Consumidor final",
        "legal_name": "Ada Compradora",
        "tax_condition": "consumidor_final",
        "cuit_encrypted": profile.cuit_encrypted,
        "cuit_hash": profile.cuit_hash,
        "masked_cuit": "••-••••••••-6",
    }
    assert result.order.identity_verifications.get().order_id == result.order.pk


@pytest.mark.django_db
def test_resume_revalidates_current_fiscal_profile_snapshot(django_user_model):
    from commerce.checkout import CheckoutError, confirm_checkout, resume_checkout
    from commerce.identity_service import approve_identity_manually

    user, profile, cart, _variant = make_checkout_cart(
        django_user_model, email="fiscal-resume@example.test", sku="FISCAL-RESUME"
    )
    pending = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=PreferencePayment(),
        billing_profile=profile,
        consent=True,
        idempotency_key=uuid.uuid4(),
    )
    staff = django_user_model.objects.create_user(email="fiscal-staff@example.test", is_staff=True)
    approve_identity_manually(
        attempt=pending.order.identity_verifications.get(),
        actor=staff,
        reason="Documento verificado",
    )
    profile.legal_name = "Razón social actualizada"
    profile.save(update_fields=("legal_name",))

    with pytest.raises(CheckoutError) as error:
        resume_checkout(
            order=pending.order,
            cart=cart,
            user=user,
            payment_adapter=PreferencePayment(),
        )
    assert error.value.code == "checkout_changed"


@pytest.mark.django_db
def test_sid_timeout_enters_review_and_rejected_attempt_cannot_be_manually_approved(
    django_user_model,
):
    from commerce.identity_service import approve_identity_manually, validate_identity
    from commerce.models import IdentityVerification
    from providers import ProviderTimeout

    user, _profile, cart, _variant = make_checkout_cart(
        django_user_model, email="sid-timeout@example.test", sku="SID-TIMEOUT"
    )
    order = pending_order(cart)

    class TimeoutSID:
        def verify(self, **kwargs):
            del kwargs
            raise ProviderTimeout("slow", diagnostics="read_timeout")

    attempt = validate_identity(
        customer=user.customer_profile, adapter=TimeoutSID(), consent=True, order=order
    )
    assert attempt.status == IdentityVerification.Status.PENDING_REVIEW

    rejected = IdentityVerification.objects.create(
        user=user,
        order=order,
        consent_version="privacy-v1",
        consented_at=timezone.now(),
        status=IdentityVerification.Status.REJECTED,
    )
    staff = django_user_model.objects.create_user(email="sid-staff@example.test", is_staff=True)
    with pytest.raises(ValidationError, match="pending review"):
        approve_identity_manually(attempt=rejected, actor=staff, reason="No corresponde")


@pytest.mark.django_db
def test_cpa8_lookup_is_exact_when_cp4_has_multiple_rows():
    from locations.models import PostalLocality
    from locations.services import lookup_localities

    now = timezone.now()
    for suffix in ("ABC", "DEF"):
        PostalLocality.objects.create(
            provider_id=f"loc-{suffix}",
            postal_code="1414",
            cpa=f"C1414{suffix}",
            locality=f"Barrio {suffix}",
            province="CABA",
            synced_at=now,
        )

    assert [row.cpa for row in lookup_localities("C1414ABC")] == ["C1414ABC"]


def test_disabled_adapters_raise_typed_failures_for_every_interface_method():
    from commerce.provider_config import UnconfiguredPaymentAdapter
    from commerce.shipping import DisabledCarrierAdapter
    from providers import ProviderNotConfigured

    payment = UnconfiguredPaymentAdapter()
    carrier = DisabledCarrierAdapter()
    calls = [
        lambda: payment.create_preference(),
        lambda: payment.fetch_payment("1"),
        lambda: payment.find_payment(external_reference="ref", preference_id="pref"),
        lambda: payment.refund("1", idempotency_key="key"),
        lambda: carrier.quote(),
        lambda: carrier.import_shipment({}, idempotency_key="key"),
        lambda: carrier.shipment_status("1"),
        lambda: carrier.label("1"),
        lambda: carrier.tracking("1"),
    ]
    for call in calls:
        with pytest.raises(ProviderNotConfigured):
            call()


def test_http_transport_applies_separate_connect_and_read_timeouts(monkeypatch):
    from providers import UrllibJsonTransport

    events = []

    class Socket:
        def settimeout(self, value):
            events.append(("read_timeout", value))

    class Response:
        status = 200

        def read(self):
            return b'{"ok": true}'

    class Connection:
        def __init__(self, host, port=None, timeout=None, context=None):
            del context
            events.append(("connect_timeout", host, port, timeout))
            self.sock = Socket()

        def connect(self):
            events.append(("connect",))

        def request(self, method, path, body=None, headers=None):
            events.append(("request", method, path, body, headers))

        def getresponse(self):
            return Response()

        def close(self):
            events.append(("close",))

    monkeypatch.setattr("providers.HTTPSConnection", Connection)
    status, body = UrllibJsonTransport().request(
        "GET", "https://provider.example.test/path", timeout=(1.5, 7.5)
    )

    assert status == 200 and body == {"ok": True}
    assert events[0] == ("connect_timeout", "provider.example.test", None, 1.5)
    assert ("read_timeout", 7.5) in events


def signed_headers(*, data_id, request_id, secret, now):
    timestamp = str(int(now.timestamp()))
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{timestamp};"
    signature = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-request-id": request_id, "x-signature": f"ts={timestamp},v1={signature}"}


@pytest.mark.django_db
def test_valid_webhook_retry_replaces_invalid_delivery_without_dedupe_poisoning(
    django_capture_on_commit_callbacks,
):
    from commerce.models import PaymentWebhookEvent
    from commerce.payments import WebhookRejected, ingest_webhook

    now = timezone.now()
    raw = json.dumps({"id": "evt-poison", "type": "payment"}).encode()
    with pytest.raises(WebhookRejected):
        ingest_webhook(
            raw_body=raw,
            data_id="PAY-42",
            headers={"x-request-id": "req-1", "x-signature": "ts=1,v1=bad"},
            secret="secret",
            enqueue=lambda pk: None,
            now=now,
            tolerance_seconds=30,
        )
    queued = []
    with django_capture_on_commit_callbacks(execute=True):
        result = ingest_webhook(
            raw_body=raw,
            data_id="PAY-42",
            headers=signed_headers(data_id="PAY-42", request_id="req-1", secret="secret", now=now),
            secret="secret",
            enqueue=queued.append,
            now=now,
            tolerance_seconds=30,
        )

    event = PaymentWebhookEvent.objects.get(event_id="evt-poison")
    assert result.duplicate is False
    assert event.payment_id == "PAY-42"
    assert event.signature_valid is True
    assert event.status == "queued"
    assert queued == [event.pk]


@pytest.mark.django_db
@override_settings(MERCADOPAGO_WEBHOOK_SECRET="secret", MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS=30)
def test_webhook_api_signs_query_data_id_and_uses_configured_tolerance(client):
    now = timezone.now()
    raw = json.dumps({"id": "evt-query", "type": "payment"})
    headers = signed_headers(data_id="ABC-123", request_id="req-query", secret="secret", now=now)
    response = client.post(
        "/api/v1/payments/mercadopago/webhook/?data.id=ABC-123",
        data=raw,
        content_type="application/json",
        HTTP_X_REQUEST_ID="req-query",
        HTTP_X_SIGNATURE=headers["x-signature"],
    )
    assert response.status_code == 202


@pytest.mark.django_db
def test_webhook_failures_requeue_and_stale_processing_events_are_swept(monkeypatch):
    from commerce.models import PaymentWebhookEvent
    from commerce.tasks import process_payment_webhook, sweep_stale_webhook_events
    from providers import ProviderTimeout

    event = PaymentWebhookEvent.objects.create(
        event_id="evt-retry",
        request_id="req",
        payment_id="42",
        raw_body_hash="a" * 64,
        signature_valid=True,
        status="queued",
    )

    def timeout(*args, **kwargs):
        del args, kwargs
        raise ProviderTimeout("slow")

    monkeypatch.setattr("commerce.tasks.process_webhook_event", timeout)
    monkeypatch.setattr("commerce.tasks.get_payment_adapter", lambda: object())
    with pytest.raises(ProviderTimeout):
        process_payment_webhook.run(event.pk)
    event.refresh_from_db()
    assert event.status == "queued"

    PaymentWebhookEvent.objects.filter(pk=event.pk).update(
        status="processing", updated_at=timezone.now() - timezone.timedelta(minutes=10)
    )
    queued_event = PaymentWebhookEvent.objects.create(
        event_id="evt-queued-lost",
        request_id="req-queued",
        payment_id="43",
        raw_body_hash="b" * 64,
        signature_valid=True,
        status="queued",
    )
    PaymentWebhookEvent.objects.filter(pk=queued_event.pk).update(
        updated_at=timezone.now() - timezone.timedelta(minutes=10)
    )
    queued = []
    assert sweep_stale_webhook_events(enqueue=queued.append, now=timezone.now()) == 2
    event.refresh_from_db()
    assert event.status == "queued"
    assert queued == [event.pk, queued_event.pk]


@pytest.mark.django_db
def test_reconciliation_searches_pending_transaction_without_payment_id(
    monkeypatch, django_user_model
):
    from commerce.models import Cart, CartLine
    from commerce.tasks import reconcile_pending_payments

    user = django_user_model.objects.create_user(email="reconcile@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="RECONCILE"), quantity=1)
    transaction = make_transaction(pending_order(cart))

    class Adapter:
        def find_payment(self, *, external_reference, preference_id):
            assert external_reference == str(transaction.external_reference)
            assert preference_id is None
            return valid_payment(transaction)

    monkeypatch.setattr("commerce.tasks.get_payment_adapter", Adapter)
    assert reconcile_pending_payments() == 1
    transaction.refresh_from_db()
    assert transaction.status == "approved"


@pytest.mark.django_db
def test_payment_requires_provider_order_metadata_and_flags_terminal_external_changes(
    django_user_model,
):
    from commerce.models import Cart, CartLine
    from commerce.payments import PaymentMismatch, apply_payment

    user = django_user_model.objects.create_user(email="binding@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="BINDING"), quantity=1)
    order = pending_order(cart)
    payment_transaction = make_transaction(order)
    mismatched = valid_payment(payment_transaction)
    mismatched["metadata"] = {"order_id": str(uuid.uuid4())}
    with pytest.raises(PaymentMismatch):
        apply_payment(transaction=payment_transaction, payment=mismatched)
    payment_transaction.refresh_from_db()
    assert payment_transaction.staff_diagnostics == "order_mismatch"

    second = make_transaction(order)
    refunded = valid_payment(second) | {
        "id": "payment-refunded",
        "status": "refunded",
        "metadata": {"order_id": str(order.public_id)},
    }
    with pytest.raises(PaymentMismatch):
        apply_payment(transaction=second, payment=refunded)
    second.refresh_from_db()
    assert second.status == "needs_attention"
    assert second.staff_diagnostics == "provider_terminal_refunded"


def test_mercadopago_preference_binds_order_metadata_and_searches_external_reference():
    from commerce.mercadopago import MercadoPagoAdapter

    order_id = uuid.UUID("39fc546f-155b-4eb6-a83f-8c4ae22b5eb9")
    external_reference = uuid.UUID("cba0963a-9060-4f83-84e5-90cf50b5f757")
    transport = ContractTransport(
        [
            (201, {"id": "pref", "init_point": "https://pay.example.test"}),
            (200, {"results": [{"id": 42, "external_reference": str(external_reference)}]}),
        ]
    )
    adapter = MercadoPagoAdapter(
        access_token="token",
        webhook_secret="secret",
        back_url_base="https://shop.example.test",
        transport=transport,
    )
    adapter.create_preference(
        external_reference=str(external_reference),
        order_id=str(order_id),
        amount=Decimal("10"),
        description="Pedido",
        payer_email="buyer@example.test",
        idempotency_key="idem",
        now=timezone.now(),
    )
    found = adapter.find_payment(external_reference=str(external_reference), preference_id="pref")

    assert transport.calls[0]["json"]["metadata"] == {"order_id": str(order_id)}
    assert transport.calls[1]["url"].endswith("/v1/payments/search")
    assert transport.calls[1]["params"] == {"external_reference": str(external_reference)}
    assert found["id"] == 42


@pytest.mark.django_db
def test_refund_waits_for_approved_total_refund_before_stock_or_status_changes(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.payments import refund_order
    from commerce.services import create_reservation, transition_order_status

    user = django_user_model.objects.create_user(email="refund-pending@example.test")
    variant = make_variant(sku="REFUND-PENDING", on_hand=2)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = pending_order(cart)
    reservation = create_reservation(variant=variant, quantity=1, reference=str(order.public_id))
    order.reservations.add(reservation)
    payment = make_transaction(order)
    payment.payment_id = "payment-1"
    payment.status = payment.Status.APPROVED
    payment.save(update_fields=("payment_id", "status", "updated_at"))
    transition_order_status(order=order, field="payment_status", value="paid")

    class PendingRefund:
        def refund(self, payment_id, *, amount=None, idempotency_key):
            assert payment_id == "payment-1"
            assert amount is None
            assert idempotency_key
            return {"id": "refund-1", "status": "pending"}

    refund = refund_order(order=order, adapter=PendingRefund(), idempotency_key=uuid.uuid4())
    variant.refresh_from_db()
    order.refresh_from_db()
    payment.refresh_from_db()
    assert refund.status == "pending"
    assert refund.stock_restored is False
    assert variant.on_hand == 2
    assert order.payment_status == "paid"
    assert payment.status == "approved"


@pytest.mark.django_db
def test_same_refund_idempotency_key_can_observe_later_provider_approval(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.payments import refund_order
    from commerce.services import create_reservation, transition_order_status

    user = django_user_model.objects.create_user(email="refund-retry@example.test")
    variant = make_variant(sku="REFUND-RETRY", on_hand=2)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = pending_order(cart)
    reservation = create_reservation(variant=variant, quantity=1, reference=str(order.public_id))
    order.reservations.add(reservation)
    payment = make_transaction(order)
    payment.payment_id = "payment-retry"
    payment.status = payment.Status.APPROVED
    payment.save(update_fields=("payment_id", "status", "updated_at"))
    transition_order_status(order=order, field="payment_status", value="paid")

    class RefundSequence:
        def __init__(self):
            self.statuses = iter(("pending", "approved"))

        def refund(self, payment_id, *, amount=None, idempotency_key):
            del payment_id, amount, idempotency_key
            return {"id": "refund-retry", "status": next(self.statuses)}

    adapter = RefundSequence()
    key = uuid.uuid4()
    first = refund_order(order=order, adapter=adapter, idempotency_key=key)
    second = refund_order(order=order, adapter=adapter, idempotency_key=key)

    assert first.pk == second.pk
    assert second.status == "approved"
    assert second.stock_restored is False
    order.refresh_from_db()
    assert order.payment_status == "refunded"


@pytest.mark.django_db
def test_shipment_creation_is_idempotent_and_requires_paid_verified_shipping_order(
    django_user_model,
):
    from commerce.models import Cart, CartLine, ShippingQuote
    from commerce.services import create_pending_identity_order, transition_order_status
    from commerce.shipping import ShipmentError, create_order_shipment

    user = django_user_model.objects.create_user(email="shipment@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="SHIPMENT"), quantity=1)
    order = pending_order(cart)

    class Adapter:
        calls = 0

        def import_shipment(self, payload, *, idempotency_key):
            self.calls += 1
            assert payload["customerId"] == "customer"
            assert idempotency_key
            return {"createdAt": "2026-08-19T12:00:00-03:00"}

    adapter = Adapter()
    with pytest.raises(ShipmentError) as error:
        create_order_shipment(order=order, adapter=adapter)
    assert error.value.code == "shipment_not_eligible"

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
        cart_fingerprint="a" * 64,
        expires_at=timezone.now() + timezone.timedelta(minutes=15),
    )
    eligible = create_pending_identity_order(
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
    transition_order_status(order=eligible, field="identity_status", value="verified")
    transition_order_status(order=eligible, field="payment_status", value="paid")
    eligible.refresh_from_db()
    shipment = create_order_shipment(order=eligible, adapter=adapter)
    duplicate = create_order_shipment(order=eligible, adapter=adapter)
    assert duplicate.pk == shipment.pk
    assert adapter.calls == 1


@pytest.mark.django_db
def test_staff_actions_return_stable_json_for_missing_order_and_missing_shipment(
    client, django_user_model
):
    from commerce.models import Cart, CartLine

    staff = django_user_model.objects.create_user(
        email="api-staff@example.test", email_verified_at=timezone.now(), is_staff=True
    )
    client.force_login(staff)
    unknown = uuid.uuid4()
    response = client.post(f"/api/v1/orders/{unknown}/shipment/", content_type="application/json")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["code"] == "order_not_found"

    cart = Cart.objects.create(user=staff)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="NO-SHIPMENT"), quantity=1)
    order = pending_order(cart)
    label = client.post(f"/api/v1/orders/{order.public_id}/label/", content_type="application/json")
    assert label.status_code == 404
    assert label.json()["code"] == "shipment_not_found"


@pytest.mark.django_db
def test_identity_api_returns_stable_json_for_typed_provider_failure(
    client, django_user_model, monkeypatch
):
    from providers import ProviderInvalidResponse

    user = django_user_model.objects.create_user(
        email="identity-provider-api@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    client.force_login(user)

    class InvalidSID:
        def verify(self, **kwargs):
            del kwargs
            raise ProviderInvalidResponse("bad payload", diagnostics="missing_status")

    monkeypatch.setattr("api_views.get_sid_adapter", InvalidSID)
    response = client.post(
        "/api/v1/identity/validate/",
        {"consent": True},
        content_type="application/json",
    )

    assert response.status_code == 502
    assert response.json() == {
        "code": "invalid_response",
        "detail": "El servicio externo devolvió una respuesta inválida.",
    }


def test_production_provider_configuration_fails_closed():
    from config.settings import validate_runtime_environment
    from tests.test_settings import production_environment

    with pytest.raises(ImproperlyConfigured, match="SID"):
        validate_runtime_environment(production_environment(SID_MODE="production"))
    with pytest.raises(ImproperlyConfigured, match="MERCADOPAGO"):
        validate_runtime_environment(production_environment(MERCADOPAGO_ACCESS_TOKEN="token-only"))
    with pytest.raises(ImproperlyConfigured, match="CORREO_ARGENTINO"):
        validate_runtime_environment(production_environment(CORREO_ARGENTINO_ENABLED="true"))


@pytest.mark.django_db
def test_sensitive_operational_admin_models_are_read_only(rf, django_user_model):
    from commerce.models import (
        ExternalProviderFailure,
        IdentityVerification,
        NotificationAttempt,
        PaymentTransaction,
        PaymentWebhookEvent,
        Refund,
        Shipment,
    )

    request = rf.get("/admin/")
    request.user = django_user_model.objects.create_superuser(email="admin-r1@example.test")
    for model in (
        PaymentTransaction,
        PaymentWebhookEvent,
        Refund,
        Shipment,
        ExternalProviderFailure,
        NotificationAttempt,
        IdentityVerification,
    ):
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_delete_permission(request) is False
        assert set(model_admin.get_readonly_fields(request)) == {
            field.name for field in model._meta.fields
        }
