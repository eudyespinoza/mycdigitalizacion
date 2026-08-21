import pytest
from rest_framework.test import APIClient

from landing.models import SiteSettings


def owner_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="social-owner@example.test",
        password="Safe-password-2026",
    )
    client = APIClient()
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_social_and_whatsapp_settings_round_trip_to_the_storefront(django_user_model):
    client = owner_client(django_user_model)

    response = client.patch(
        "/api/v1/management/settings/general/",
        {
            "instagram_url": "https://instagram.com/mycdigitalizacion",
            "facebook_url": "https://facebook.com/mycdigitalizacion",
            "tiktok_url": "https://tiktok.com/@mycdigitalizacion",
            "youtube_url": "",
            "linkedin_url": "https://linkedin.com/company/mycdigitalizacion",
            "whatsapp_enabled": True,
            "whatsapp_number": "+54 9 11 5555-1234",
            "whatsapp_message": "Hola, quiero consultar por un producto",
        },
        format="json",
    )

    assert response.status_code == 200
    settings = SiteSettings.objects.get(pk=1)
    assert settings.whatsapp_number == "5491155551234"
    public = client.get("/api/v1/storefront/home/").json()["settings"]
    assert public["instagram_url"] == "https://instagram.com/mycdigitalizacion"
    assert public["youtube_url"] == ""
    assert public["whatsapp_enabled"] is True
    assert public["whatsapp_number"] == "5491155551234"
    assert public["whatsapp_message"] == "Hola, quiero consultar por un producto"


@pytest.mark.django_db
def test_social_settings_reject_insecure_urls_and_invalid_enabled_whatsapp(django_user_model):
    client = owner_client(django_user_model)

    response = client.patch(
        "/api/v1/management/settings/general/",
        {
            "instagram_url": "http://instagram.com/mycdigitalizacion",
            "whatsapp_enabled": True,
            "whatsapp_number": "123",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "instagram_url" in response.json()
    assert "whatsapp_number" in response.json()


@pytest.mark.django_db
def test_openapi_exposes_social_and_whatsapp_settings(django_user_model):
    client = owner_client(django_user_model)
    schemas = client.get("/api/v1/schema/?format=json").json()["components"]["schemas"]

    public = schemas["SiteSettings"]["properties"]
    management = schemas["GeneralSettings"]["properties"]
    for field in (
        "instagram_url",
        "facebook_url",
        "tiktok_url",
        "youtube_url",
        "linkedin_url",
        "whatsapp_enabled",
        "whatsapp_number",
        "whatsapp_message",
    ):
        assert field in public
        assert field in management
