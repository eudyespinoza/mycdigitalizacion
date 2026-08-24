import pytest
from django.test import override_settings
from django.utils import timezone


@pytest.mark.django_db
@override_settings(SID_MODE="disabled")
def test_identity_status_marks_verification_as_not_required(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="identity-status-disabled@example.test",
        email_verified_at=timezone.now(),
    )
    client.force_login(user)

    response = client.get("/api/v1/identity/status/")

    assert response.status_code == 200
    assert response.json() == {"status": "not_required", "required": False}


@pytest.mark.django_db
@override_settings(SID_MODE="disabled")
def test_stale_identity_validation_request_is_a_noop_when_sid_is_disabled(
    client, django_user_model
):
    from commerce.models import IdentityVerification

    user = django_user_model.objects.create_user(
        email="identity-validate-disabled@example.test",
        email_verified_at=timezone.now(),
    )
    client.force_login(user)

    response = client.post(
        "/api/v1/identity/validate/",
        {"consent": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "not_required", "required": False}
    assert not IdentityVerification.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_identity_status_still_requires_verification_for_configured_adapter(
    client, django_user_model, monkeypatch
):
    class ConfiguredSID:
        verification_required = True

    monkeypatch.setattr("api_views.get_sid_adapter", ConfiguredSID)
    user = django_user_model.objects.create_user(
        email="identity-status-configured@example.test",
        email_verified_at=timezone.now(),
    )
    client.force_login(user)

    response = client.get("/api/v1/identity/status/")

    assert response.status_code == 200
    assert response.json() == {"status": "not_started", "required": True}


def test_incomplete_stored_sid_configuration_is_treated_as_not_configured(monkeypatch):
    from commerce.identity import DisabledSIDAdapter
    from commerce.provider_config import get_sid_adapter

    monkeypatch.setattr(
        "commerce.provider_config._stored",
        lambda provider: {
            "enabled": True,
            "public_config": {"base_url": "https://sid.example.test"},
            "secrets": {"access_token": ""},
        }
        if provider == "sid_renaper"
        else None,
    )

    assert isinstance(get_sid_adapter(), DisabledSIDAdapter)
