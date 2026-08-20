import json
import uuid
from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from tests.test_commerce_domain import make_variant
from tests.test_task4_storefront_contracts import make_address, verified_user

CSRF_BODY = {
    "code": "csrf_failed",
    "detail": "La sesión de seguridad venció. Actualizá la página e intentá nuevamente.",
}


@pytest.mark.django_db
def test_api_csrf_middleware_returns_stable_safe_json_for_missing_and_rotated_tokens(
    django_user_model,
):
    user = verified_user(django_user_model, "csrf-round2@example.test")
    browser = Client(enforce_csrf_checks=True)

    missing = browser.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "Correct-Horse-Battery-Staple-42"},
        content_type="application/json",
    )
    initial_token = browser.get("/api/v1/auth/csrf/").json()["csrf_token"]
    logged_in = browser.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "Correct-Horse-Battery-Staple-42"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=initial_token,
    )
    rotated = browser.patch(
        "/api/v1/customers/me/",
        json.dumps({"first_name": "Ada"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=initial_token,
    )
    fresh_token = browser.get("/api/v1/auth/csrf/").json()["csrf_token"]
    retried_once = browser.patch(
        "/api/v1/customers/me/",
        json.dumps({"first_name": "Ada"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=fresh_token,
    )

    assert logged_in.status_code == 200
    for response in (missing, rotated):
        assert response.status_code == 403
        assert response.headers["Content-Type"].startswith("application/json")
        assert response.json() == CSRF_BODY
        assert "CSRF" not in response.content.decode()
    assert retried_once.status_code == 200


@pytest.mark.django_db
def test_far_reverse_coordinates_can_confirm_the_original_written_address(
    client, django_user_model
):
    user = verified_user(django_user_model, "written-after-reverse@example.test")
    address = make_address(
        user,
        raw_address="Calle Uno 123",
        normalized_address="CALLE UNO 123, CABA",
        latitude=Decimal("-34.6100000"),
        longitude=Decimal("-58.3900000"),
        geocode_source="manual",
        geocode_summary={
            "reverse_location": {"locality": "Palermo", "province": "CABA"}
        },
    )
    client.force_login(user)

    response = client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6100000",
            "longitude": "-58.3900000",
            "address_choice": "written",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    address.refresh_from_db()
    assert address.raw_address == "Calle Uno 123"
    assert address.normalized_address == "CALLE UNO 123, CABA"
    assert (str(address.latitude), str(address.longitude)) == (
        "-34.6100000",
        "-58.3900000",
    )
    assert address.geocode_summary["confirmation"]["address_choice"] == "written"


@pytest.mark.django_db
def test_reverse_choice_accepts_and_persists_the_reverse_normalized_result(
    client, django_user_model
):
    user = verified_user(django_user_model, "accept-reverse@example.test")
    address = make_address(
        user,
        raw_address="Calle Uno 123",
        normalized_address="CALLE UNO 123, CABA",
        latitude=Decimal("-34.6100000"),
        longitude=Decimal("-58.3900000"),
        geocode_source="manual",
        geocode_summary={
            "reverse_location": {"locality": "Palermo", "province": "CABA"}
        },
    )
    client.force_login(user)

    response = client.post(
        f"/api/v1/addresses/{address.pk}/confirm/",
        {
            "latitude": "-34.6100000",
            "longitude": "-58.3900000",
            "address_choice": "reverse",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    address.refresh_from_db()
    assert address.raw_address == "Calle Uno 123"
    assert address.normalized_address == "Palermo, CABA"
    assert address.geocode_summary["confirmation"]["address_choice"] == "reverse"


@pytest.mark.django_db
@override_settings(SID_MODE="disabled")
def test_explicitly_disabled_pickup_is_rejected_before_identity_or_payment(
    client, django_user_model
):
    from landing.models import SiteSettings
    from tests.test_checkout_domain import make_billing_profile, make_customer

    user = django_user_model.objects.create_user(
        email="pickup-disabled@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing = make_billing_profile(user)
    from commerce.models import Cart, CartLine

    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart,
        variant=make_variant(sku="PICKUP-DISABLED", on_hand=5),
        quantity=1,
    )
    SiteSettings.objects.create(pickup_enabled=False)
    client.force_login(user)

    response = client.post(
        "/api/v1/checkout/",
        {
            "fulfillment_method": "pickup",
            "billing_profile_id": billing.pk,
            "consent": True,
            "idempotency_key": str(uuid.uuid4()),
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "pickup_unavailable",
        "detail": "El retiro no está disponible en este momento.",
    }
    assert not user.identity_verifications.exists()
    assert not user.orders.exists()


@pytest.mark.django_db
def test_absent_or_default_site_settings_publish_pickup_as_enabled(client):
    from landing.models import SiteSettings

    absent = client.get("/api/v1/storefront/home/")
    created = SiteSettings.objects.create()
    present = client.get("/api/v1/storefront/home/")

    assert absent.json()["settings"]["pickup_enabled"] is True
    assert created.pickup_enabled is True
    assert present.json()["settings"]["pickup_enabled"] is True


@pytest.mark.django_db
def test_resume_converts_stock_race_to_stable_checkout_error(django_user_model):
    from commerce.checkout import CheckoutError, confirm_checkout, resume_checkout
    from commerce.identity_service import approve_identity_manually
    from tests.test_checkout_domain import UnavailableSID, make_billing_profile, make_customer
    from tests.test_commerce_domain import make_variant

    user = django_user_model.objects.create_user(
        email="resume-stock@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing = make_billing_profile(user)
    from commerce.models import Cart, CartLine

    cart = Cart.objects.create(user=user)
    variant = make_variant(sku="RESUME-STOCK", on_hand=1)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    pending = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=object(),
        billing_profile=billing,
        consent=True,
        idempotency_key=uuid.uuid4(),
    )
    staff = django_user_model.objects.create_user(email="resume-staff@example.test", is_staff=True)
    approve_identity_manually(
        attempt=pending.order.identity_verifications.get(),
        actor=staff,
        reason="Documento verificado",
    )
    variant.on_hand = 0
    variant.save(update_fields=("on_hand",))

    with pytest.raises(CheckoutError) as error:
        resume_checkout(
            order=pending.order,
            cart=cart,
            user=user,
            payment_adapter=object(),
        )

    assert error.value.code == "insufficient_stock"


@pytest.mark.django_db
def test_resume_rechecks_explicit_pickup_disable_before_payment(django_user_model):
    from commerce.checkout import CheckoutError, confirm_checkout, resume_checkout
    from commerce.identity_service import approve_identity_manually
    from commerce.models import Cart, CartLine
    from landing.models import SiteSettings
    from tests.test_checkout_domain import UnavailableSID, make_billing_profile, make_customer

    user = django_user_model.objects.create_user(
        email="resume-pickup-disabled@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing = make_billing_profile(user)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart,
        variant=make_variant(sku="RESUME-PICKUP-DISABLED", on_hand=1),
        quantity=1,
    )
    pending = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="pickup",
        sid_adapter=UnavailableSID(),
        payment_adapter=object(),
        billing_profile=billing,
        consent=True,
        idempotency_key=uuid.uuid4(),
    )
    staff = django_user_model.objects.create_user(
        email="resume-pickup-staff@example.test", is_staff=True
    )
    approve_identity_manually(
        attempt=pending.order.identity_verifications.get(),
        actor=staff,
        reason="Documento verificado",
    )
    SiteSettings.objects.create(pickup_enabled=False)

    with pytest.raises(CheckoutError) as error:
        resume_checkout(
            order=pending.order,
            cart=cart,
            user=user,
            payment_adapter=object(),
        )

    assert error.value.code == "pickup_unavailable"
    assert not pending.order.payment_transactions.exists()


@pytest.mark.django_db
def test_openapi_enumerates_real_csrf_checkout_resume_and_provider_codes(client):
    schema = client.get("/api/v1/schema/?format=json").json()
    components = schema["components"]["schemas"]

    def property_enum(component, property_name):
        property_schema = component["properties"][property_name]
        if "$ref" in property_schema:
            property_schema = components[property_schema["$ref"].rsplit("/", 1)[-1]]
        return property_schema["enum"]

    login_403 = schema["paths"]["/api/v1/auth/login/"]["post"]["responses"]["403"]
    csrf_ref = login_403["content"]["application/json"]["schema"]["$ref"]
    csrf_schema = components[csrf_ref.rsplit("/", 1)[-1]]
    assert property_enum(csrf_schema, "code") == ["csrf_failed"]

    checkout = schema["paths"]["/api/v1/checkout/"]["post"]["responses"]
    resume = schema["paths"]["/api/v1/checkout/{public_id}/resume/"]["post"]["responses"]
    checkout_400_schema = checkout["400"]["content"]["application/json"]["schema"]
    domain_schema = next(
        item for item in checkout_400_schema["oneOf"] if "properties" in item
    )
    domain_codes = set(domain_schema["properties"]["code"]["enum"])
    assert domain_codes == {
        "invalid_fulfillment",
        "pickup_unavailable",
        "address_required",
        "address_review_required",
        "shipping_quote_required",
        "shipping_quote_expired",
        "shipping_quote_changed",
        "cart_owner_mismatch",
        "invalid_email",
        "email_not_verified",
        "identity_consent_required",
        "identity_missing",
        "billing_profile_invalid",
        "empty_cart",
        "insufficient_stock",
    }
    resume_ref = resume["400"]["content"]["application/json"]["schema"]["$ref"]
    resume_codes = set(
        property_enum(components[resume_ref.rsplit("/", 1)[-1]], "code")
    )
    assert resume_codes == {
        "identity_pending_review",
        "cart_owner_mismatch",
        "checkout_changed",
        "pickup_unavailable",
        "insufficient_stock",
    }
    for responses in (checkout, resume):
        assert {"501", "502", "503"} <= set(responses)
        provider_ref = responses["503"]["content"]["application/json"]["schema"]["$ref"]
        provider_codes = set(
            property_enum(components[provider_ref.rsplit("/", 1)[-1]], "code")
        )
        assert provider_codes == {
            "not_configured",
            "unavailable",
            "timeout",
            "invalid_response",
            "rejected",
            "not_supported",
        }
