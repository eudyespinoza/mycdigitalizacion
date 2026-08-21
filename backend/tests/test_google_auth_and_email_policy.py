from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomerProfile, EmailVerificationChallenge, Profile
from backoffice.models import IntegrationConfiguration
from backoffice.secrets import seal_secret_map

pytestmark = pytest.mark.django_db


REGISTRATION = {
    "email": "new-customer@example.test",
    "password": "StrongPassword!2026",
    "first_name": "Ana",
    "last_name": "Pérez",
    "phone": "+54 11 5555 1234",
    "consent_version": "privacy-v1",
}


def configure_smtp():
    return IntegrationConfiguration.objects.create(
        provider="smtp",
        enabled=True,
        environment="production",
        public_config={
            "host": "smtp.example.test",
            "port": 587,
            "use_tls": True,
            "from_email": "ventas@example.test",
        },
        sealed_secrets=seal_secret_map(
            {"username": "mailer", "password": "smtp-password"}
        ),
    )


def configure_google():
    return IntegrationConfiguration.objects.create(
        provider="google_identity",
        enabled=True,
        environment="production",
        public_config={"client_id": "web-client.apps.googleusercontent.com"},
    )


def test_registration_auto_verifies_email_when_transactional_email_is_unavailable(
    django_user_model,
):
    response = APIClient().post("/api/v1/auth/register/", REGISTRATION, format="json")

    assert response.status_code == 201
    user = django_user_model.objects.get(email=REGISTRATION["email"])
    assert user.email_verified_at is not None
    assert not EmailVerificationChallenge.objects.filter(user=user).exists()


@override_settings(CONFIG_ENCRYPTION_MASTER_KEY="smtp-policy-test-key")
def test_registration_requires_verification_only_with_complete_enabled_smtp(
    django_user_model,
):
    configure_smtp()

    response = APIClient().post("/api/v1/auth/register/", REGISTRATION, format="json")

    assert response.status_code == 201
    user = django_user_model.objects.get(email=REGISTRATION["email"])
    assert user.email_verified_at is None
    assert EmailVerificationChallenge.objects.filter(user=user).exists()


def test_existing_unverified_user_is_unblocked_on_login_when_smtp_is_unavailable(
    django_user_model,
):
    user = django_user_model.objects.create_user(
        email="pending@example.test",
        password="StrongPassword!2026",
    )
    Profile.objects.create(user=user)
    CustomerProfile.objects.create(user=user, consent_version="privacy-v1")

    response = APIClient().post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "StrongPassword!2026"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified_at is not None


def test_auth_configuration_hides_google_until_the_integration_is_enabled():
    client = APIClient()
    disabled = client.get("/api/v1/auth/config/")
    assert disabled.status_code == 200
    assert disabled.json() == {
        "email_verification_required": False,
        "google_enabled": False,
        "google_client_id": "",
    }

    configure_google()
    enabled = client.get("/api/v1/auth/config/")
    assert enabled.json() == {
        "email_verification_required": False,
        "google_enabled": True,
        "google_client_id": "web-client.apps.googleusercontent.com",
    }


def google_claims(**overrides):
    return {
        "sub": "google-subject-123",
        "email": "linked@example.test",
        "email_verified": True,
        "given_name": "Eudy",
        "family_name": "Espinoza",
        **overrides,
    }


def test_google_login_links_a_verified_matching_email_and_uses_the_stable_subject(
    django_user_model,
):
    configure_google()
    user = django_user_model.objects.create_user(
        email="linked@example.test",
        password="StrongPassword!2026",
    )
    Profile.objects.create(user=user)
    CustomerProfile.objects.create(user=user, consent_version="privacy-v1")

    with patch(
        "accounts.google_identity.verify_google_token",
        return_value=google_claims(),
    ):
        client = APIClient()
        response = client.post(
            "/api/v1/auth/google/",
            {"credential": "signed-google-id-token", "mode": "login"},
            format="json",
        )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified_at is not None
    identity = user.external_identities.get(provider="google")
    assert identity.subject == "google-subject-123"
    assert client.get("/api/v1/customers/me/").status_code == 200


def test_google_login_rejects_unverified_email_claims_without_linking_an_account(
    django_user_model,
):
    configure_google()
    user = django_user_model.objects.create_user(
        email="linked@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )

    with patch(
        "accounts.google_identity.verify_google_token",
        return_value=google_claims(email_verified=False),
    ):
        response = APIClient().post(
            "/api/v1/auth/google/",
            {"credential": "unverified-token", "mode": "login"},
            format="json",
        )

    assert response.status_code == 400
    assert response.json()["code"] == "google_email_not_verified"
    assert not user.external_identities.exists()


def test_new_google_customer_requires_registration_details_then_creates_an_account(
    django_user_model,
):
    configure_google()
    claims = google_claims(email="new-google@example.test", sub="new-google-subject")
    client = APIClient()

    with patch("accounts.google_identity.verify_google_token", return_value=claims):
        login_response = client.post(
            "/api/v1/auth/google/",
            {"credential": "new-token", "mode": "login"},
            format="json",
        )
        registration_response = client.post(
            "/api/v1/auth/google/",
            {
                "credential": "new-token",
                "mode": "register",
                "phone": "+54 11 4444 3333",
                "consent_version": "privacy-v1",
            },
            format="json",
        )

    assert login_response.status_code == 409
    assert login_response.json()["code"] == "google_registration_required"
    assert registration_response.status_code == 201
    user = django_user_model.objects.get(email="new-google@example.test")
    assert not user.has_usable_password()
    assert user.email_verified_at is not None
    assert user.profile.first_name == "Eudy"
    assert user.profile.last_name == "Espinoza"
    assert user.profile.phone == "+54 11 4444 3333"
    assert user.customer_profile.consent_version == "privacy-v1"
    assert user.external_identities.get(provider="google").subject == "new-google-subject"
