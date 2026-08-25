import base64
import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from backoffice.integrations import serialize_configuration
from backoffice.models import IntegrationConfiguration, ManagementAuditEvent
from backoffice.secrets import unseal_secret_map

pytestmark = pytest.mark.django_db

OAUTH_SETTINGS = {
    "CONFIG_ENCRYPTION_MASTER_KEY": "oauth-config-master-key-for-tests",
    "PUBLIC_BACKEND_URL": "https://shop.example.test",
    "MERCADOPAGO_OAUTH_CLIENT_ID": "1234567890123456",
    "MERCADOPAGO_OAUTH_CLIENT_SECRET": "oauth-client-secret",
    "MERCADOPAGO_OAUTH_REDIRECT_URI": (
        "https://shop.example.test/api/v1/payments/mercadopago/oauth/callback/"
    ),
    "MERCADOPAGO_WEBHOOK_SECRET": "webhook-secret",
}

EMPTY_OAUTH_SETTINGS = {
    "CONFIG_ENCRYPTION_MASTER_KEY": "oauth-config-master-key-for-tests",
    "PUBLIC_BACKEND_URL": "https://shop.example.test",
    "MERCADOPAGO_OAUTH_CLIENT_ID": "",
    "MERCADOPAGO_OAUTH_CLIENT_SECRET": "",
    "MERCADOPAGO_OAUTH_REDIRECT_URI": (
        "https://shop.example.test/api/v1/payments/mercadopago/oauth/callback/"
    ),
    "MERCADOPAGO_WEBHOOK_SECRET": "",
}


def create_owner(django_user_model):
    return django_user_model.objects.create_superuser(
        email="oauth-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )


def owner_client(django_user_model):
    client = APIClient()
    owner = create_owner(django_user_model)
    client.force_login(owner)
    return client, owner


@override_settings(**EMPTY_OAUTH_SETTINGS)
def test_owner_configures_oauth_application_in_admin_without_webhook(
    django_user_model,
):
    client, _ = owner_client(django_user_model)

    saved = client.patch(
        "/api/v1/management/integrations/mercadopago/",
        {
            "environment": "production",
            "public_config": {"oauth_client_id": "app-123456"},
            "secrets": {"oauth_client_secret": "protected-app-secret"},
        },
        format="json",
    )

    assert saved.status_code == 200
    assert saved.json()["oauth_ready"] is True
    assert saved.json()["webhook_ready"] is False
    assert saved.json()["oauth_status"] == "disconnected"
    assert saved.json()["secret_fields"]["oauth_client_secret"] is True
    assert "protected-app-secret" not in json.dumps(saved.json())
    configuration = IntegrationConfiguration.objects.get(provider="mercadopago")
    assert "protected-app-secret" not in configuration.sealed_secrets

    started = client.post(
        "/api/v1/management/integrations/mercadopago/oauth/start/", format="json"
    )
    assert started.status_code == 200
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    assert query["client_id"] == ["app-123456"]


@override_settings(**EMPTY_OAUTH_SETTINGS)
def test_owner_verifies_saved_oauth_application_before_connecting(
    django_user_model,
):
    client, _ = owner_client(django_user_model)
    saved = client.patch(
        "/api/v1/management/integrations/mercadopago/",
        {
            "environment": "production",
            "public_config": {"oauth_client_id": "app-ready"},
            "secrets": {"oauth_client_secret": "saved-secret"},
        },
        format="json",
    )
    assert saved.status_code == 200

    verified = client.post(
        "/api/v1/management/integrations/mercadopago/test/", format="json"
    )

    assert verified.status_code == 200
    assert verified.json()["last_test_status"] == "pending"
    assert "aplicación está preparada" in verified.json()["last_test_message"].lower()
    assert verified.json()["webhook_ready"] is False


@override_settings(**EMPTY_OAUTH_SETTINGS)
def test_disconnect_keeps_saved_application_and_webhook_configuration(
    django_user_model,
):
    from commerce.mercadopago_oauth import store_oauth_credentials

    client, owner = owner_client(django_user_model)
    saved = client.patch(
        "/api/v1/management/integrations/mercadopago/",
        {
            "environment": "production",
            "public_config": {"oauth_client_id": "app-987654"},
            "secrets": {
                "oauth_client_secret": "saved-client-secret",
                "webhook_secret": "saved-webhook-secret",
            },
        },
        format="json",
    )
    assert saved.status_code == 200
    store_oauth_credentials(
        {
            "access_token": "connected-access",
            "refresh_token": "connected-refresh",
            "user_id": "445566",
            "live_mode": True,
            "expires_in": 15_552_000,
        },
        actor=owner,
    )

    disconnected = client.post(
        "/api/v1/management/integrations/mercadopago/oauth/disconnect/", format="json"
    )

    assert disconnected.status_code == 200
    assert disconnected.json()["oauth_ready"] is True
    assert disconnected.json()["webhook_ready"] is True
    assert disconnected.json()["oauth_status"] == "disconnected"
    configuration = IntegrationConfiguration.objects.get(provider="mercadopago")
    assert configuration.public_config["oauth_client_id"] == "app-987654"
    assert unseal_secret_map(configuration.sealed_secrets) == {
        "oauth_client_secret": "saved-client-secret",
        "webhook_secret": "saved-webhook-secret",
    }


@override_settings(**OAUTH_SETTINGS)
def test_authorization_session_uses_static_redirect_state_and_pkce_s256(django_user_model):
    from commerce.mercadopago_oauth import create_authorization_session

    cache.clear()
    owner = create_owner(django_user_model)
    authorization_url = create_authorization_session(owner.id)
    query = parse_qs(urlsplit(authorization_url).query)

    assert urlsplit(authorization_url)._replace(query="").geturl() == (
        "https://auth.mercadopago.com.ar/authorization"
    )
    assert query["client_id"] == ["1234567890123456"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == [OAUTH_SETTINGS["MERCADOPAGO_OAUTH_REDIRECT_URI"]]
    assert query["code_challenge_method"] == ["S256"]
    assert "code_verifier" not in query
    assert "oauth-owner@example.test" not in authorization_url


@override_settings(**OAUTH_SETTINGS)
def test_oauth_state_is_single_use_and_returns_the_server_side_verifier(django_user_model):
    from commerce.mercadopago_oauth import (
        MercadoPagoOAuthStateError,
        consume_authorization_state,
        create_authorization_session,
    )

    cache.clear()
    owner = create_owner(django_user_model)
    authorization_url = create_authorization_session(owner.id)
    state = parse_qs(urlsplit(authorization_url).query)["state"][0]

    payload = consume_authorization_state(state)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(payload.code_verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    assert payload.actor_id == owner.id
    assert 43 <= len(payload.code_verifier) <= 128
    assert challenge == parse_qs(urlsplit(authorization_url).query)["code_challenge"][0]
    with pytest.raises(MercadoPagoOAuthStateError):
        consume_authorization_state(state)


@override_settings(**OAUTH_SETTINGS)
def test_oauth_credentials_are_encrypted_serialized_safely_and_enable_checkout(
    django_user_model,
):
    from commerce.mercadopago_oauth import store_oauth_credentials
    from commerce.provider_config import get_payment_adapter

    owner = create_owner(django_user_model)
    configuration = store_oauth_credentials(
        {
            "access_token": "APP_USR-private-access",
            "refresh_token": "TG-private-refresh",
            "user_id": 99887766,
            "live_mode": True,
            "expires_in": 15_552_000,
        },
        actor=owner,
    )

    configuration.refresh_from_db()
    assert "APP_USR-private-access" not in configuration.sealed_secrets
    assert "TG-private-refresh" not in configuration.sealed_secrets
    assert unseal_secret_map(configuration.sealed_secrets) == {
        "access_token": "APP_USR-private-access",
        "refresh_token": "TG-private-refresh",
        "webhook_secret": "webhook-secret",
    }
    serialized = serialize_configuration("mercadopago", configuration)
    assert serialized["oauth_status"] == "connected"
    assert serialized["connected_account_id"] == "99887766"
    assert "APP_USR-private-access" not in json.dumps(serialized)
    assert "TG-private-refresh" not in json.dumps(serialized)
    adapter = get_payment_adapter()
    assert adapter.access_token == "APP_USR-private-access"
    assert adapter.collector_id == "99887766"
    assert adapter.live_mode is True


@override_settings(**OAUTH_SETTINGS)
def test_expiring_oauth_token_refreshes_and_rotates_refresh_token(django_user_model):
    from commerce.mercadopago_oauth import (
        resolve_oauth_access_token,
        store_oauth_credentials,
    )

    owner = create_owner(django_user_model)
    configuration = store_oauth_credentials(
        {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "user_id": "5511",
            "live_mode": False,
            "expires_in": 1,
        },
        actor=owner,
    )
    configuration.public_config["token_expires_at"] = (
        timezone.now() - timedelta(minutes=1)
    ).isoformat()
    configuration.save(update_fields=("public_config", "updated_at"))

    def token_request(payload):
        assert payload["grant_type"] == "refresh_token"
        assert payload["refresh_token"] == "old-refresh"
        return {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "user_id": "5511",
            "live_mode": False,
            "expires_in": 15_552_000,
        }

    assert resolve_oauth_access_token(token_request=token_request) == "new-access"
    configuration.refresh_from_db()
    secrets = unseal_secret_map(configuration.sealed_secrets)
    assert secrets["refresh_token"] == "new-refresh"
    assert secrets["access_token"] == "new-access"


@override_settings(**OAUTH_SETTINGS)
def test_own_account_connects_with_client_credentials_and_validates_the_account(
    django_user_model,
):
    from commerce.mercadopago_oauth import connect_own_mercadopago_account
    from commerce.provider_config import get_payment_adapter

    owner = create_owner(django_user_model)
    observed = {}

    def token_request(payload):
        observed["token_payload"] = payload
        return {
            "access_token": "APP_USR-own-account-access",
            "expires_in": 21_600,
            "token_type": "Bearer",
        }

    def account_request(access_token):
        observed["account_access_token"] = access_token
        return {
            "id": 99887766,
            "site_id": "MLA",
            "status": "active",
        }

    configuration = connect_own_mercadopago_account(
        actor=owner,
        token_request=token_request,
        account_request=account_request,
    )

    assert observed == {
        "token_payload": {
            "client_id": "1234567890123456",
            "client_secret": "oauth-client-secret",
            "grant_type": "client_credentials",
        },
        "account_access_token": "APP_USR-own-account-access",
    }
    configuration.refresh_from_db()
    assert configuration.enabled is True
    assert configuration.environment == "production"
    assert configuration.public_config["oauth_grant_type"] == "client_credentials"
    assert configuration.public_config["collector_id"] == "99887766"
    assert configuration.public_config["connected_account_site_id"] == "MLA"
    assert unseal_secret_map(configuration.sealed_secrets) == {
        "access_token": "APP_USR-own-account-access",
        "webhook_secret": "webhook-secret",
    }
    serialized = serialize_configuration("mercadopago", configuration)
    assert serialized["oauth_status"] == "connected"
    assert "APP_USR-own-account-access" not in json.dumps(serialized)
    adapter = get_payment_adapter()
    assert adapter.access_token == "APP_USR-own-account-access"
    assert adapter.collector_id == "99887766"
    assert adapter.live_mode is True


@override_settings(**OAUTH_SETTINGS)
def test_expired_client_credentials_token_is_renewed_without_refresh_token(
    django_user_model,
):
    from commerce.mercadopago_oauth import (
        connect_own_mercadopago_account,
        resolve_oauth_access_token,
    )

    owner = create_owner(django_user_model)
    configuration = connect_own_mercadopago_account(
        actor=owner,
        token_request=lambda payload: {
            "access_token": "old-own-access",
            "expires_in": 1,
        },
        account_request=lambda access_token: {
            "id": 5511,
            "site_id": "MLA",
            "status": "active",
        },
    )
    configuration.public_config["token_expires_at"] = (
        timezone.now() - timedelta(minutes=1)
    ).isoformat()
    configuration.save(update_fields=("public_config", "updated_at"))

    def token_request(payload):
        assert payload == {
            "client_id": "1234567890123456",
            "client_secret": "oauth-client-secret",
            "grant_type": "client_credentials",
        }
        return {"access_token": "renewed-own-access", "expires_in": 21_600}

    assert resolve_oauth_access_token(
        token_request=token_request,
        account_request=lambda access_token: {
            "id": 5511,
            "site_id": "MLA",
            "status": "active",
        },
    ) == "renewed-own-access"
    configuration.refresh_from_db()
    assert unseal_secret_map(configuration.sealed_secrets)["access_token"] == (
        "renewed-own-access"
    )
    assert "refresh_token" not in unseal_secret_map(configuration.sealed_secrets)


@override_settings(**OAUTH_SETTINGS)
def test_owner_connects_own_account_without_external_authorization(
    monkeypatch,
    django_user_model,
):
    client, owner = owner_client(django_user_model)
    monkeypatch.setattr(
        "commerce.mercadopago_oauth._default_token_request",
        lambda payload: {
            "access_token": "management-own-access",
            "expires_in": 21_600,
        },
    )
    monkeypatch.setattr(
        "commerce.mercadopago_oauth._default_account_request",
        lambda access_token: {
            "id": 778899,
            "site_id": "MLA",
            "status": "active",
            "company": {"brand_name": "La Torre"},
        },
    )

    connected = client.post(
        "/api/v1/management/integrations/mercadopago/connect/", format="json"
    )

    assert connected.status_code == 200
    assert connected.json()["oauth_status"] == "connected"
    assert connected.json()["connected_account_id"] == "778899"
    assert connected.json()["public_config"]["connected_brand_name"] == "La Torre"
    assert "authorization_url" not in connected.json()
    assert ManagementAuditEvent.objects.filter(
        actor=owner,
        action="integration.oauth_connected",
        object_reference="mercadopago",
    ).exists()


@override_settings(**OAUTH_SETTINGS)
def test_owner_can_start_callback_and_disconnect_oauth(monkeypatch, django_user_model):
    client, owner = owner_client(django_user_model)
    cache.clear()
    started = client.post(
        "/api/v1/management/integrations/mercadopago/oauth/start/", format="json"
    )

    assert started.status_code == 200
    authorization_url = started.json()["authorization_url"]
    state = parse_qs(urlsplit(authorization_url).query)["state"][0]

    monkeypatch.setattr(
        "backoffice.oauth_views.exchange_authorization_code",
        lambda code, code_verifier: {
            "access_token": "callback-access",
            "refresh_token": "callback-refresh",
            "user_id": "778899",
            "live_mode": False,
            "expires_in": 15_552_000,
        },
    )
    callback = client.get(
        "/api/v1/payments/mercadopago/oauth/callback/",
        {"code": "authorization-code", "state": state},
    )

    assert callback.status_code == 302
    assert callback["Location"] == (
        "https://shop.example.test/gestion/integraciones/mercadopago?mp_oauth=connected"
    )
    assert IntegrationConfiguration.objects.get(provider="mercadopago").enabled is True
    assert ManagementAuditEvent.objects.filter(
        actor=owner,
        action="integration.oauth_connected",
        object_reference="mercadopago",
    ).exists()

    disconnected = client.post(
        "/api/v1/management/integrations/mercadopago/oauth/disconnect/", format="json"
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["oauth_status"] == "disconnected"
    configuration = IntegrationConfiguration.objects.get(provider="mercadopago")
    assert unseal_secret_map(configuration.sealed_secrets) == {
        "webhook_secret": "webhook-secret"
    }
    assert configuration.enabled is False


@override_settings(**OAUTH_SETTINGS)
def test_non_owner_cannot_start_or_disconnect_mercadopago(django_user_model):
    staff = django_user_model.objects.create_user(
        email="catalog-oauth@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
        is_staff=True,
    )
    client = APIClient()
    client.force_login(staff)

    assert client.post(
        "/api/v1/management/integrations/mercadopago/oauth/start/", format="json"
    ).status_code == 403
    assert client.post(
        "/api/v1/management/integrations/mercadopago/connect/", format="json"
    ).status_code == 403
    assert client.post(
        "/api/v1/management/integrations/mercadopago/oauth/disconnect/", format="json"
    ).status_code == 403


@override_settings(
    CONFIG_ENCRYPTION_MASTER_KEY="oauth-config-master-key-for-tests",
    PUBLIC_BACKEND_URL="https://shop.example.test",
    MERCADOPAGO_OAUTH_CLIENT_ID="",
    MERCADOPAGO_OAUTH_CLIENT_SECRET="",
    MERCADOPAGO_OAUTH_REDIRECT_URI="",
    MERCADOPAGO_WEBHOOK_SECRET="",
)
def test_unprepared_oauth_is_reported_without_rendering_secret_fields(django_user_model):
    client, _ = owner_client(django_user_model)

    detail = client.get("/api/v1/management/integrations/mercadopago/")
    started = client.post(
        "/api/v1/management/integrations/mercadopago/oauth/start/", format="json"
    )

    assert detail.status_code == 200
    assert detail.json()["oauth_ready"] is False
    assert detail.json()["oauth_status"] == "not_ready"
    assert started.status_code == 409
    assert started.json()["code"] == "mercadopago_oauth_not_configured"


@override_settings(**OAUTH_SETTINGS)
def test_openapi_documents_oauth_start_callback_and_disconnect(django_user_model):
    client, _ = owner_client(django_user_model)
    paths = client.get("/api/v1/schema/?format=json").json()["paths"]

    assert "/api/v1/management/integrations/mercadopago/oauth/start/" in paths
    assert "/api/v1/management/integrations/mercadopago/connect/" in paths
    assert "/api/v1/payments/mercadopago/oauth/callback/" in paths
    assert "/api/v1/management/integrations/mercadopago/oauth/disconnect/" in paths
