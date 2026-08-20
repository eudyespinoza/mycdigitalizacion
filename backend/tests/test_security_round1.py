import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import Client
from django.utils import timezone

from accounts.models import BillingProfile, CustomerProfile, EmailVerificationChallenge


def csrf_client():
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    return client, token


@pytest.mark.django_db
def test_login_requires_a_valid_csrf_token():
    user = get_user_model().objects.create_user(
        email="verified-login@example.test",
        password="Correct-Horse-Battery-Staple-42",
        email_verified_at=timezone.now(),
    )
    client = Client(enforce_csrf_checks=True)
    payload = {"email": user.email, "password": "Correct-Horse-Battery-Staple-42"}

    assert client.post("/api/v1/auth/login/", payload).status_code == 403
    client, token = csrf_client()
    assert (
        client.post("/api/v1/auth/login/", payload, HTTP_X_CSRFTOKEN="invalid").status_code
        == 403
    )
    response = client.post("/api/v1/auth/login/", payload, HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 200
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_logout_requires_a_valid_csrf_token():
    user = get_user_model().objects.create_user(email="logout@example.test")
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    assert client.post("/api/v1/auth/logout/").status_code == 403
    token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    assert client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204


@pytest.mark.django_db
def test_unverified_user_cannot_mutate_customer_pii_but_verified_user_can():
    user = get_user_model().objects.create_user(email="unverified@example.test")
    client = Client()
    client.force_login(user)
    payload = {
        "label": "Casa sintética",
        "raw_address": "Calle Sintética 123",
        "street": "Calle Sintética",
        "number": "123",
        "postal_code": "1000",
        "locality": "CABA",
        "province": "CABA",
    }

    assert client.post("/api/v1/addresses/", payload).status_code == 403
    assert client.post("/api/v1/checkout/", {}).status_code == 403
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    assert client.post("/api/v1/addresses/", payload).status_code == 201
    assert client.post("/api/v1/checkout/", {}).status_code == 503


@pytest.mark.django_db
def test_verification_challenge_locks_after_five_failed_attempts():
    user = get_user_model().objects.create_user(email="attempts@example.test")
    challenge = EmailVerificationChallenge.issue(user=user, code="123456")

    for _ in range(5):
        response = Client().post(
            "/api/v1/auth/email-verify/", {"email": user.email, "code": "000000"}
        )
        assert response.status_code == 400

    challenge.refresh_from_db()
    assert challenge.attempt_count == 5
    assert challenge.locked_at is not None
    assert (
        Client().post(
            "/api/v1/auth/email-verify/", {"email": user.email, "code": "123456"}
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_verification_endpoint_throttles_repeated_email_and_ip_attempts():
    user = get_user_model().objects.create_user(email="throttle@example.test")
    EmailVerificationChallenge.issue(user=user, code="123456")
    client = Client(REMOTE_ADDR="203.0.113.10")

    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/email-verify/", {"email": user.email, "code": "000000"}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/auth/email-verify/", {"email": user.email, "code": "000000"}
        ).status_code
        == 429
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        (
            {
                "email": "not-an-email",
                "password": "Correct-Horse-Battery-Staple-42",
                "consent_version": "privacy-v1",
            },
            400,
        ),
        (
            {
                "email": "valid@example.test",
                "password": "password",
                "consent_version": "privacy-v1",
            },
            400,
        ),
        (
            {
                "email": "valid@example.test",
                "password": "Correct-Horse-Battery-Staple-42",
                "consent_version": "invented-v9",
            },
            400,
        ),
    ],
)
def test_registration_validates_email_password_and_server_consent(payload, expected_status):
    assert Client().post("/api/v1/auth/register/", payload).status_code == expected_status


@pytest.mark.django_db
def test_registration_casefolds_email_and_returns_conflict_for_duplicate():
    payload = {
        "email": "Mixed.Case@Example.Test",
        "password": "Correct-Horse-Battery-Staple-42",
        "consent_version": "privacy-v1",
    }

    assert Client().post("/api/v1/auth/register/", payload).status_code == 201
    assert get_user_model().objects.get().email == "mixed.case@example.test"
    duplicate = Client().post(
        "/api/v1/auth/register/", {**payload, "email": "MIXED.CASE@example.test"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"code": "email_already_registered"}


@pytest.mark.django_db
def test_dni_and_cuit_validate_length_and_checksum_before_encryption():
    user = get_user_model().objects.create_user(email="identifiers@example.test")
    customer = CustomerProfile(user=user, consent_version="privacy-v1")

    with pytest.raises(ValidationError):
        customer.set_dni("abc")
    with pytest.raises(ValidationError):
        customer.set_cuit("20-12345678-0")

    customer.set_dni("12.345.678")
    customer.set_cuit("20-12345678-6")
    customer.save()
    billing = BillingProfile(customer=customer, label="CF", legal_name="Sintético")
    billing.set_cuit("20-12345678-6")
    billing.save()
    assert customer.masked_dni == "••••5678"
    assert billing.masked_cuit == "••-••••••••-6"


@pytest.mark.django_db
def test_billing_api_rejects_invalid_cuit_without_persisting(client):
    user = get_user_model().objects.create_user(
        email="billing-invalid@example.test", email_verified_at=timezone.now()
    )
    CustomerProfile.objects.create(user=user, consent_version="privacy-v1")
    client.force_login(user)

    response = client.post(
        "/api/v1/billing-profiles/",
        {"label": "CF", "legal_name": "Sintético", "tax_condition": "CF", "cuit": "abc"},
    )

    assert response.status_code == 400
    assert not BillingProfile.objects.exists()


def test_production_rejects_the_committed_build_encryption_key():
    from config.settings import validate_runtime_environment
    from tests.test_settings import production_environment

    with pytest.raises(ImproperlyConfigured, match="PERSONAL_DATA_ENCRYPTION_KEY"):
        validate_runtime_environment(
            production_environment(
                PERSONAL_DATA_ENCRYPTION_KEY=(
                    "container-build-personal-data-encryption-key-not-for-runtime"
                )
            )
        )


@pytest.mark.django_db
def test_identity_admin_forms_only_expose_masked_values_and_validated_replacements(
    django_user_model,
):
    from accounts.admin import BillingProfileAdminForm, CustomerProfileAdminForm

    user = django_user_model.objects.create_user(email="masked-admin@example.test")
    customer = CustomerProfile.objects.create(user=user, consent_version="privacy-v1")
    customer_form = CustomerProfileAdminForm(instance=customer)
    billing_form = BillingProfileAdminForm()

    assert not {
        "dni_encrypted",
        "dni_hash",
        "cuit_encrypted",
        "cuit_hash",
    } & customer_form.fields.keys()
    assert not {"cuit_encrypted", "cuit_hash"} & billing_form.fields.keys()

    invalid = CustomerProfileAdminForm(
        data={
            "user": user.pk,
            "consent_version": "privacy-v1",
            "consented_at": "",
            "replacement_dni": "invalid",
            "replacement_cuit": "invalid",
        },
        instance=customer,
    )
    assert not invalid.is_valid()
    assert {"replacement_dni", "replacement_cuit"} <= invalid.errors.keys()
