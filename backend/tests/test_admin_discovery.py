import pytest
from django.test import override_settings

from accounts.serializers import CustomerSerializer


@pytest.mark.django_db
def test_customer_contract_exposes_staff_access_without_exposing_superuser_status(
    django_user_model,
):
    staff = django_user_model.objects.create_user(
        email="operator@example.test",
        password="safe-test-password",
        is_staff=True,
        is_superuser=True,
    )

    payload = CustomerSerializer(staff).data

    assert payload["is_staff"] is True
    assert "is_superuser" not in payload


@pytest.mark.django_db
@override_settings(
    MERCADOPAGO_ACCESS_TOKEN="TEST-SECRET-ACCESS-TOKEN",
    MERCADOPAGO_WEBHOOK_SECRET="TEST-SECRET-WEBHOOK",
    MERCADOPAGO_COLLECTOR_ID="collector-1234",
    MERCADOPAGO_LIVE_MODE=False,
)
def test_superuser_can_discover_safe_integration_status_without_secret_values(
    client,
    django_user_model,
):
    owner = django_user_model.objects.create_superuser(
        email="owner@example.test",
        password="safe-test-password",
    )
    client.force_login(owner)

    dashboard = client.get("/admin/")
    integrations = client.get("/admin/integraciones/")

    assert dashboard.status_code == 200
    assert b"Integraciones" in dashboard.content
    assert integrations.status_code == 200
    assert b"Mercado Pago" in integrations.content
    assert b"Configurado" in integrations.content
    assert b"Modo de pruebas" in integrations.content
    assert b"collector-1234" in integrations.content
    assert b"TEST-SECRET-ACCESS-TOKEN" not in integrations.content
    assert b"TEST-SECRET-WEBHOOK" not in integrations.content


@pytest.mark.django_db
def test_integration_status_rejects_non_staff_users(client, django_user_model):
    customer = django_user_model.objects.create_user(
        email="customer@example.test",
        password="safe-test-password",
    )
    client.force_login(customer)

    response = client.get("/admin/integraciones/")

    assert response.status_code == 302
    assert "/admin/login/" in response.headers["Location"]
