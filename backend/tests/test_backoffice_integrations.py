import json

import pytest
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from landing.models import SiteSettings

pytestmark = pytest.mark.django_db


def create_owner(django_user_model):
    return django_user_model.objects.create_superuser(
        email="owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )


def owner_client(django_user_model):
    client = APIClient()
    client.force_login(create_owner(django_user_model))
    return client


def test_integration_list_exposes_all_business_providers_without_secrets(django_user_model):
    response = owner_client(django_user_model).get("/api/v1/management/integrations/")

    assert response.status_code == 200
    assert [row["provider"] for row in response.json()["results"]] == [
        "mercadopago",
        "correo_argentino",
        "sid_renaper",
        "smtp",
        "geolocation",
        "backups",
    ]
    assert all("secrets" not in row for row in response.json()["results"])


@override_settings(
    CONFIG_ENCRYPTION_MASTER_KEY="integration-config-master-key-for-tests",
    PUBLIC_BACKEND_URL="https://shop.example.test",
)
def test_mercadopago_configuration_is_encrypted_write_only_and_used_by_adapter(
    django_user_model,
):
    client = owner_client(django_user_model)
    payload = {
        "enabled": True,
        "environment": "sandbox",
        "public_config": {"collector_id": "123456", "live_mode": False},
        "secrets": {
            "access_token": "TEST-secret-access-token",
            "webhook_secret": "secret-webhook-value",
        },
    }

    saved = client.patch(
        "/api/v1/management/integrations/mercadopago/", payload, format="json"
    )

    assert saved.status_code == 200
    body = saved.json()
    assert body["status"] == "configured"
    assert body["secret_fields"] == {"access_token": True, "webhook_secret": True}
    assert "TEST-secret-access-token" not in json.dumps(body)
    assert "secret-webhook-value" not in json.dumps(body)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sealed_secrets FROM backoffice_integrationconfiguration "
            "WHERE provider = %s",
            ["mercadopago"],
        )
        ciphertext = cursor.fetchone()[0]
    assert "TEST-secret-access-token" not in ciphertext
    assert "secret-webhook-value" not in ciphertext

    from commerce.provider_config import get_payment_adapter

    adapter = get_payment_adapter()
    assert adapter.access_token == "TEST-secret-access-token"
    assert adapter.webhook_secret == "secret-webhook-value"
    assert adapter.collector_id == "123456"
    assert adapter.live_mode is False


@override_settings(CONFIG_ENCRYPTION_MASTER_KEY="integration-config-master-key-for-tests")
def test_blank_secret_input_preserves_existing_value_and_explicit_clear_removes_it(
    django_user_model,
):
    client = owner_client(django_user_model)
    endpoint = "/api/v1/management/integrations/sid_renaper/"
    created = client.patch(
        endpoint,
        {
            "enabled": True,
            "environment": "sandbox",
            "public_config": {"base_url": "https://sid.example.test"},
            "secrets": {"access_token": "sid-secret"},
        },
        format="json",
    )
    assert created.status_code == 200

    preserved = client.patch(endpoint, {"secrets": {"access_token": ""}}, format="json")
    assert preserved.status_code == 200
    assert preserved.json()["secret_fields"]["access_token"] is True

    cleared = client.patch(
        endpoint, {"clear_secret_fields": ["access_token"]}, format="json"
    )
    assert cleared.status_code == 200
    assert cleared.json()["secret_fields"]["access_token"] is False
    assert cleared.json()["status"] == "incomplete"


def test_only_owner_can_change_integrations(django_user_model):
    staff = django_user_model.objects.create_user(
        email="catalog@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
        is_staff=True,
    )
    client = APIClient()
    client.force_login(staff)

    response = client.patch(
        "/api/v1/management/integrations/mercadopago/",
        {"enabled": False},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Sólo el Propietario puede cambiar integraciones."


def test_general_store_settings_are_editable_from_management(django_user_model):
    SiteSettings.objects.create(public_name="mycdigitalizacion")
    client = owner_client(django_user_model)

    updated = client.patch(
        "/api/v1/management/settings/general/",
        {
            "public_name": "mycdigitalizacion",
            "announcement": "Envíos a todo el país",
            "contact_email": "ventas@example.test",
            "pickup_enabled": True,
            "pickup_label": "Retiro en oficina",
            "pickup_address": "Av. Siempre Viva 742",
            "pickup_hours": "Lunes a viernes de 9 a 18",
        },
        format="json",
    )

    assert updated.status_code == 200
    settings = SiteSettings.objects.get(pk=1)
    assert settings.contact_email == "ventas@example.test"
    assert settings.pickup_address == "Av. Siempre Viva 742"


def test_management_openapi_documents_private_configuration_contracts(django_user_model):
    client = owner_client(django_user_model)
    schema = client.get("/api/v1/schema/?format=json").json()
    paths = schema["paths"]

    assert "/api/v1/management/session/" in paths
    assert "/api/v1/management/dashboard/" in paths
    assert "/api/v1/management/integrations/" in paths
    detail = paths["/api/v1/management/integrations/{provider}/"]
    assert detail["patch"]["requestBody"]["content"]["application/json"]["schema"]
    assert detail["patch"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "/api/v1/management/settings/general/" in paths
