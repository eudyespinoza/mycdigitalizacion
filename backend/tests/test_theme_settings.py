import pytest
from rest_framework.test import APIClient

from landing.models import SiteSettings


def owner_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="theme-owner@example.test",
        password="Safe-password-2026",
    )
    client = APIClient()
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_theme_settings_round_trip_to_management_and_storefront(django_user_model):
    client = owner_client(django_user_model)
    payload = {
        "theme_palette": "custom",
        "theme_structure": "#183B32",
        "theme_action": "#9C2F4A",
        "theme_wayfinding": "#2D6A4F",
        "theme_background": "#FAFCF7",
        "theme_text": "#183B32",
    }

    response = client.patch(
        "/api/v1/management/settings/general/",
        payload,
        format="json",
    )

    assert response.status_code == 200
    assert {key: response.json()[key] for key in payload} == payload
    settings = SiteSettings.objects.get(pk=1)
    assert settings.theme_palette == "custom"
    public = client.get("/api/v1/storefront/home/").json()["settings"]
    assert {key: public[key] for key in payload} == payload


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("override", "error_field"),
    [
        ({"theme_palette": "unknown"}, "theme_palette"),
        ({"theme_palette": "custom", "theme_action": "magenta"}, "theme_action"),
        (
            {
                "theme_palette": "custom",
                "theme_background": "#FFFFFF",
                "theme_text": "#B8B8B8",
            },
            "theme_text",
        ),
        (
            {
                "theme_palette": "custom",
                "theme_background": "#FFFFFF",
                "theme_action": "#F34887",
            },
            "theme_action",
        ),
    ],
)
def test_custom_theme_rejects_unknown_invalid_or_low_contrast_values(
    django_user_model,
    override,
    error_field,
):
    client = owner_client(django_user_model)

    response = client.patch(
        "/api/v1/management/settings/general/",
        override,
        format="json",
    )

    assert response.status_code == 400
    assert error_field in response.json()


@pytest.mark.django_db
def test_openapi_exposes_global_theme_settings(django_user_model):
    client = owner_client(django_user_model)
    schemas = client.get("/api/v1/schema/?format=json").json()["components"]["schemas"]

    for schema_name in ("SiteSettings", "GeneralSettings"):
        properties = schemas[schema_name]["properties"]
        for field in (
            "theme_palette",
            "theme_structure",
            "theme_action",
            "theme_wayfinding",
            "theme_background",
            "theme_text",
        ):
            assert field in properties
