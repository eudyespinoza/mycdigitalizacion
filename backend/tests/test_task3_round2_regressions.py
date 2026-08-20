import json
import uuid
from http.client import BadStatusLine, IncompleteRead, RemoteDisconnected

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.utils import timezone

from tests.test_checkout_domain import ApprovedSID, make_customer
from tests.test_commerce_domain import make_variant
from tests.test_task3_round1_regressions import make_billing_profile


def make_checkout_cart(django_user_model, *, email="round2@example.test", sku="ROUND2"):
    from commerce.models import Cart, CartLine

    user = django_user_model.objects.create_user(email=email, email_verified_at=timezone.now())
    make_customer(user)
    profile = make_billing_profile(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku=sku, on_hand=5), quantity=1)
    return user, profile, cart


@pytest.mark.django_db
def test_checkout_retry_after_provider_success_and_db_failure_reuses_preference_boundary(
    django_user_model, monkeypatch
):
    from commerce import checkout as checkout_module
    from commerce.checkout import confirm_checkout
    from commerce.mercadopago import CheckoutPreference
    from commerce.models import IdentityVerification, Order, PaymentTransaction

    user, profile, cart = make_checkout_cart(django_user_model)
    key = uuid.UUID("79365bd7-f549-4bd7-a014-dd1f81f9e6b2")

    class Payment:
        collector_id = "collector"
        live_mode = False

        def __init__(self):
            self.calls = []
            self.preferences = {}

        def create_preference(self, **kwargs):
            self.calls.append(kwargs)
            preference = self.preferences.setdefault(
                kwargs["idempotency_key"],
                CheckoutPreference(
                    f"pref-{len(self.preferences) + 1}",
                    f"https://pay.example.test/{len(self.preferences) + 1}",
                    kwargs["now"] + timezone.timedelta(minutes=20),
                ),
            )
            return preference

    payment = Payment()
    transition = checkout_module.transition_order_status
    failed = False

    def fail_after_provider(*, order, field, value):
        nonlocal failed
        if field == "payment_status" and not failed:
            failed = True
            raise DatabaseError("injected commit boundary failure")
        return transition(order=order, field=field, value=value)

    monkeypatch.setattr(checkout_module, "transition_order_status", fail_after_provider)
    with pytest.raises(DatabaseError, match="injected"):
        confirm_checkout(
            cart=cart,
            user=user,
            fulfillment_method="pickup",
            sid_adapter=ApprovedSID(),
            payment_adapter=payment,
            billing_profile=profile,
            consent=True,
            idempotency_key=key,
        )

    assert not Order.objects.exists()
    assert not PaymentTransaction.objects.exists()
    assert not IdentityVerification.objects.filter(order__isnull=True).exists()

    result = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=ApprovedSID(),
        payment_adapter=payment,
        billing_profile=profile,
        consent=True,
        idempotency_key=key,
    )

    assert len(payment.calls) == 2
    assert payment.calls[0]["idempotency_key"] == payment.calls[1]["idempotency_key"]
    assert payment.calls[0]["external_reference"] == payment.calls[1]["external_reference"]
    assert result.transaction.preference_id == "pref-1"
    assert IdentityVerification.objects.filter(order=result.order).count() == 1
    assert not IdentityVerification.objects.filter(order__isnull=True).exists()


@pytest.mark.django_db
def test_webhook_claim_refreshes_timestamp_before_provider_io_and_is_not_swept():
    from commerce.models import PaymentWebhookEvent
    from commerce.payments import process_webhook_event
    from commerce.tasks import sweep_stale_webhook_events
    from providers import ProviderTimeout

    event = PaymentWebhookEvent.objects.create(
        event_id="evt-active-claim",
        request_id="req-active-claim",
        payment_id="pay-active-claim",
        raw_body_hash="a" * 64,
        signature_valid=True,
        status="queued",
    )
    stale_at = timezone.now() - timezone.timedelta(minutes=10)
    PaymentWebhookEvent.objects.filter(pk=event.pk).update(updated_at=stale_at)
    queued = []

    class Adapter:
        def fetch_payment(self, payment_id):
            assert payment_id == "pay-active-claim"
            assert sweep_stale_webhook_events(enqueue=queued.append, now=timezone.now()) == 0
            raise ProviderTimeout("slow")

    with pytest.raises(ProviderTimeout):
        process_webhook_event(event=event, adapter=Adapter())
    event.refresh_from_db()
    assert event.status == "processing"
    assert event.updated_at > stale_at
    assert queued == []


@pytest.mark.parametrize(
    "protocol_error",
    [RemoteDisconnected(), BadStatusLine("bad"), IncompleteRead(b"x", 2)],
)
def test_http_protocol_failures_are_typed(monkeypatch, protocol_error):
    from providers import ProviderError, UrllibJsonTransport

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            del args, kwargs

        def connect(self):
            return None

        def request(self, *args, **kwargs):
            del args, kwargs

        def getresponse(self):
            raise protocol_error

        def close(self):
            return None

    monkeypatch.setattr("providers.HTTPSConnection", Connection)
    with pytest.raises(ProviderError) as error:
        UrllibJsonTransport().request("GET", "https://provider.example.test/data")
    assert error.value.code in {"unavailable", "invalid_response"}


@pytest.mark.parametrize("status_code", [400, 402])
def test_provider_validation_responses_are_rejected_without_retry(status_code):
    from providers import ProviderHttpClient, ProviderRejected

    class Transport:
        calls = 0

        def request(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            return status_code, {"message": "validation"}

    transport = Transport()
    with pytest.raises(ProviderRejected):
        ProviderHttpClient(transport, retries=3).request_json(
            "POST", "https://provider.example.test/data", payload={}, idempotent=True
        )
    assert transport.calls == 1


def eligible_shipping_order(django_user_model, *, parcel_count=2):
    from commerce.models import Cart, CartLine, ShippingQuote
    from commerce.services import create_pending_identity_order, transition_order_status

    user = django_user_model.objects.create_user(email=f"shipping-{uuid.uuid4()}@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku=f"SHIP-{uuid.uuid4()}"), quantity=1)
    parcels = [
        {
            "box_code": f"box-{index}",
            "weight_grams": 1000,
            "length_cm": "10",
            "width_cm": "10",
            "height_cm": "10",
        }
        for index in range(1, parcel_count + 1)
    ]
    quote = ShippingQuote.objects.create(
        user=user,
        service="multi_parcel" if parcel_count > 1 else "CP",
        postal_code="1414",
        parcels=parcels,
        base_amount="10.00",
        total_amount="10.00",
        cart_fingerprint="b" * 64,
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
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_multi_parcel_import_persists_progress_and_skips_completed_remote_call(django_user_model):
    from commerce.models import Shipment, ShipmentParcelImport
    from commerce.shipping import create_order_shipment
    from providers import ProviderUnavailable

    order = eligible_shipping_order(django_user_model)

    class Adapter:
        customer_id = "customer"

        def __init__(self):
            self.calls = []
            self.fail_second = True

        def import_shipment(self, payload, *, idempotency_key):
            self.calls.append((payload["extOrderId"], idempotency_key))
            if payload["extOrderId"].endswith("-2") and self.fail_second:
                self.fail_second = False
                raise ProviderUnavailable("carrier unavailable")
            return {"createdAt": "2026-08-20T12:00:00-03:00"}

    adapter = Adapter()
    with pytest.raises(ProviderUnavailable):
        create_order_shipment(order=order, adapter=adapter)

    shipment = Shipment.objects.get(order=order)
    assert shipment.status == "importing"
    assert list(shipment.parcel_imports.values_list("status", flat=True)) == [
        ShipmentParcelImport.Status.IMPORTED,
        ShipmentParcelImport.Status.PENDING,
    ]

    completed = create_order_shipment(order=order, adapter=adapter)
    assert completed.status == "imported"
    first_external_id = f"{order.public_id}-1"
    assert [call[0] for call in adapter.calls].count(first_external_id) == 1
    assert adapter.calls[1][1] == adapter.calls[2][1]


@pytest.mark.django_db
def test_multi_parcel_final_db_failure_retries_without_duplicate_provider_shipments(
    django_user_model, monkeypatch
):
    from commerce.models import Shipment
    from commerce.shipping import create_order_shipment

    order = eligible_shipping_order(django_user_model)

    class Adapter:
        customer_id = "customer"

        def __init__(self):
            self.calls = []

        def import_shipment(self, payload, *, idempotency_key):
            self.calls.append((payload["extOrderId"], idempotency_key))
            return {"createdAt": "2026-08-20T12:00:00-03:00"}

    adapter = Adapter()
    original_save = Shipment.save
    failed = False

    def fail_final_save(instance, *args, **kwargs):
        nonlocal failed
        if instance.status == "imported" and not failed:
            failed = True
            raise DatabaseError("injected shipment finalization failure")
        return original_save(instance, *args, **kwargs)

    monkeypatch.setattr(Shipment, "save", fail_final_save)
    with pytest.raises(DatabaseError, match="finalization"):
        create_order_shipment(order=order, adapter=adapter)
    assert Shipment.objects.get(order=order).status == "importing"
    assert Shipment.objects.get(order=order).parcel_imports.filter(status="imported").count() == 2

    shipment = create_order_shipment(order=order, adapter=adapter)
    assert shipment.status == "imported"
    assert len(adapter.calls) == 2


@pytest.mark.django_db
def test_checkout_sid_rejection_returns_stable_safe_json(client, django_user_model, monkeypatch):
    from providers import ProviderRejected

    user, profile, _cart = make_checkout_cart(
        django_user_model, email="sid-rejected-api@example.test", sku="SID-REJECTED-R2"
    )
    client.force_login(user)

    class RejectedSID:
        def verify(self, **kwargs):
            del kwargs
            raise ProviderRejected("sensitive upstream details", diagnostics="document_mismatch")

    monkeypatch.setattr("api_views.get_sid_adapter", RejectedSID)
    response = client.post(
        "/api/v1/checkout/",
        {
            "fulfillment_method": "pickup",
            "billing_profile_id": profile.pk,
            "consent": True,
            "idempotency_key": str(uuid.uuid4()),
        },
        content_type="application/json",
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "identity_rejected",
        "detail": "No pudimos validar tu identidad.",
    }


@pytest.mark.django_db
def test_webhook_openapi_documents_signed_headers_query_body_and_responses(client):
    response = client.get("/api/v1/schema/?format=json")
    assert response.status_code == 200
    schema = json.loads(response.content)
    operation = schema["paths"]["/api/v1/payments/mercadopago/webhook/"]["post"]
    parameters = {(item["in"], item["name"]): item for item in operation["parameters"]}
    assert parameters[("query", "data.id")]["required"] is True
    assert parameters[("header", "x-signature")]["required"] is True
    assert parameters[("header", "x-request-id")]["required"] is True
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    assert {"id", "type", "data"}.issubset(set(body.get("required", ())))
    assert set(operation["responses"]) >= {"200", "202", "403"}


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"MERCADOPAGO_LIVE_MODE": "truthy"}, "MERCADOPAGO_LIVE_MODE"),
        ({"CORREO_ARGENTINO_ENABLED": "tru"}, "CORREO_ARGENTINO_ENABLED"),
        (
            {
                "MERCADOPAGO_ACCESS_TOKEN": "access",
                "MERCADOPAGO_WEBHOOK_SECRET": "secret",
                "MERCADOPAGO_LIVE_MODE": "false",
            },
            "MERCADOPAGO_COLLECTOR_ID",
        ),
    ],
)
def test_provider_boolean_and_mercadopago_startup_validation_is_fail_closed(overrides, match):
    from config.settings import validate_runtime_environment
    from tests.test_settings import production_environment

    with pytest.raises(ImproperlyConfigured, match=match):
        validate_runtime_environment(production_environment(**overrides))


def test_mercadopago_configuration_requires_collector_outside_production_too():
    from config.settings import validate_runtime_environment

    with pytest.raises(ImproperlyConfigured, match="MERCADOPAGO_COLLECTOR_ID"):
        validate_runtime_environment(
            {
                "APP_ENV": "development",
                "MERCADOPAGO_ACCESS_TOKEN": "access",
                "MERCADOPAGO_WEBHOOK_SECRET": "secret",
                "MERCADOPAGO_LIVE_MODE": "false",
            }
        )


@pytest.mark.django_db
def test_public_order_api_whitelists_fiscal_snapshot_fields(client, django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import create_pending_identity_order

    user = django_user_model.objects.create_user(
        email="fiscal-public@example.test", email_verified_at=timezone.now()
    )
    client.force_login(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="FISCAL-PUBLIC"), quantity=1)
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={},
        fiscal_snapshot={
            "profile_id": 99,
            "label": "Empresa",
            "legal_name": "Empresa SA",
            "tax_condition": "responsable_inscripto",
            "masked_cuit": "••-••••••••-6",
            "cuit_encrypted": "encrypted-secret",
            "cuit_hash": "hash-secret",
        },
        fulfillment_method="pickup",
    )
    response = client.get(f"/api/v1/orders/{order.public_id}/")
    assert response.status_code == 200
    assert response.json()["fiscal_snapshot"] == {
        "label": "Empresa",
        "legal_name": "Empresa SA",
        "tax_condition": "responsable_inscripto",
        "masked_cuit": "••-••••••••-6",
    }
