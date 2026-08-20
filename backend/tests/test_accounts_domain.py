import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


def test_user_identity_is_a_unique_email_without_username():
    user_model = get_user_model()

    assert user_model.USERNAME_FIELD == "email"
    assert user_model._meta.get_field("email").unique is True
    assert not any(field.name == "username" for field in user_model._meta.fields)


@pytest.mark.django_db
def test_email_verification_challenge_expires_after_fifteen_minutes():
    from accounts.models import EmailVerificationChallenge

    user = get_user_model().objects.create_user(email="synthetic@example.test")
    challenge = EmailVerificationChallenge.issue(user=user, code="123456")

    assert challenge.verify("123456", now=challenge.created_at + timezone.timedelta(minutes=14))
    assert not challenge.verify(
        "123456", now=challenge.created_at + timezone.timedelta(minutes=15, seconds=1)
    )
    assert not challenge.verify("654321", now=challenge.created_at)


@pytest.mark.django_db
def test_sensitive_tax_identifiers_are_encrypted_hashed_and_masked():
    from accounts.models import CustomerProfile

    user = get_user_model().objects.create_user(email="private@example.test")
    profile = CustomerProfile(user=user, consent_version="privacy-v1")
    profile.set_dni("12345678")
    profile.set_cuit("20123456786")
    profile.save()

    stored = CustomerProfile.objects.get(pk=profile.pk)
    assert "12345678" not in stored.dni_encrypted
    assert stored.dni_hash and stored.dni_hash != "12345678"
    assert stored.get_dni() == "12345678"
    assert stored.masked_dni == "••••5678"
    assert stored.masked_cuit == "••-••••••••-6"
