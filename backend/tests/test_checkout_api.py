import json

import pytest
from django.test import override_settings
from django.utils import timezone

from tests.test_checkout_domain import make_billing_profile, make_customer
from tests.test_commerce_domain import make_variant


@pytest.mark.django_db
def test_postal_lookup_returns_only_matching_cached_rows(client):
    from locations.models import PostalLocality

    now = timezone.now()
    PostalLocality.objects.create(
        provider_id="one",
        postal_code="1414",
        cpa="C1414ABC",
        locality="Villa Crespo",
        province="CABA",
        synced_at=now,
    )
    PostalLocality.objects.create(
        provider_id="two",
        postal_code="5000",
        cpa="X5000AAA",
        locality="Córdoba",
        province="Córdoba",
        synced_at=now,
    )

    response = client.get("/api/v1/locations/postal-lookup/?postal_code=c1414abc")

    assert response.status_code == 200
    assert response.json() == [
        {
            "postal_code": "1414",
            "cpa": "C1414ABC",
            "locality": "Villa Crespo",
            "province": "CABA",
        }
    ]


@pytest.mark.django_db
@override_settings(SID_MODE="disabled")
def test_checkout_api_skips_identity_review_when_sid_disabled(
    client, django_user_model, monkeypatch
):
    from commerce.models import Cart, CartLine
    from tests.test_checkout_domain import PreferencePayment

    monkeypatch.setattr("api_views.get_payment_adapter", PreferencePayment)

    user = django_user_model.objects.create_user(
        email="api-checkout@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing_profile = make_billing_profile(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="API-CHECKOUT"), quantity=1)
    client.force_login(user)

    response = client.post(
        "/api/v1/checkout/",
        {
            "fulfillment_method": "pickup",
            "billing_profile_id": billing_profile.pk,
            "consent": False,
            "idempotency_key": "3b88cc2a-3484-4d9e-892a-60fc8cb0949c",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["identity_status"] == "verified"
    assert response.json()["checkout_url"] == "https://pay.example.test/preference"


@pytest.mark.django_db
@override_settings(MERCADOPAGO_WEBHOOK_SECRET="webhook-secret")
def test_webhook_api_persists_invalid_signature_with_stable_safe_error(client):
    from commerce.models import PaymentWebhookEvent

    body = {"id": "evt-api", "type": "payment", "data": {"id": "99"}}
    response = client.post(
        "/api/v1/payments/mercadopago/webhook/?data.id=99",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_X_REQUEST_ID="req-api",
        HTTP_X_SIGNATURE="ts=1,v1=bad",
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "invalid_webhook_signature",
        "detail": "No pudimos validar la notificación de pago.",
    }
    assert PaymentWebhookEvent.objects.get(event_id="evt-api").status == "rejected"


@pytest.mark.django_db
def test_payment_status_ignores_redirect_query_parameters(client, django_user_model):
    from commerce.models import Cart, CartLine, PaymentTransaction
    from tests.test_checkout_domain import make_transaction, pending_order

    user = django_user_model.objects.create_user(
        email="payment-status@example.test", email_verified_at=timezone.now()
    )
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="STATUS"), quantity=1)
    transaction = make_transaction(pending_order(cart))
    client.force_login(user)

    response = client.get(
        f"/api/v1/payments/{transaction.external_reference}/status/?status=approved&payment_id=fake"
    )

    assert response.status_code == 200
    assert response.json()["status"] == PaymentTransaction.Status.PENDING
    assert response.json()["payment_id"] is None
