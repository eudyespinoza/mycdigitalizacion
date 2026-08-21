import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from backoffice.models import IntegrationConfiguration
from backoffice.secrets import seal_secret_map

pytestmark = pytest.mark.django_db


def authenticated_client(django_user_model):
    user = django_user_model.objects.create_user(
        email="map-customer@example.test",
        password="StrongPassword!2026",
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_map_configuration_defaults_to_openstreetmap_without_credentials(
    django_user_model,
):
    client = authenticated_client(django_user_model)
    response = client.get("/api/v1/locations/map-config/")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openstreetmap",
        "google_maps_browser_key": "",
        "google_maps_map_id": "",
    }


@override_settings(
    CONFIG_ENCRYPTION_MASTER_KEY="map-provider-config-key-for-tests"
)
def test_google_maps_is_returned_only_when_enabled_with_a_browser_key(
    django_user_model,
):
    configuration = IntegrationConfiguration.objects.create(
        provider="geolocation",
        enabled=True,
        environment="production",
        public_config={
            "provider": "google_maps",
            "google_maps_map_id": "MYC_MAP_ID",
        },
        sealed_secrets=seal_secret_map(
            {"google_maps_browser_key": "restricted-browser-key"}
        ),
    )

    client = authenticated_client(django_user_model)
    response = client.get("/api/v1/locations/map-config/")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "google_maps",
        "google_maps_browser_key": "restricted-browser-key",
        "google_maps_map_id": "MYC_MAP_ID",
    }

    configuration.enabled = False
    configuration.save(update_fields=("enabled",))
    fallback = client.get("/api/v1/locations/map-config/")
    assert fallback.json()["provider"] == "openstreetmap"


def test_geolocation_management_contract_uses_osm_or_google_browser_credentials():
    from backoffice.integrations import INTEGRATION_DEFINITIONS

    definition = INTEGRATION_DEFINITIONS["geolocation"]
    assert definition.public_fields == ("provider", "google_maps_map_id")
    assert definition.secret_fields == ("google_maps_browser_key",)
    assert definition.required_public == ("provider",)
