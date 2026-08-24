import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import database_config, validate_runtime_environment


def production_environment(**overrides: str) -> dict[str, str]:
    environment = {
        "APP_ENV": "production",
        "DJANGO_SECRET_KEY": "a-long-unpredictable-production-signing-key",
        "POSTGRES_PASSWORD": "a-long-unpredictable-database-password",
        "SITE_ADDRESS": "shop.example.com",
        "DJANGO_ALLOWED_HOSTS": "shop.example.com",
        "PERSONAL_DATA_ENCRYPTION_KEY": "a-long-unpredictable-personal-data-encryption-key",
    }
    environment.update(overrides)
    return environment


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DJANGO_SECRET_KEY", "unsafe-development-key-change-me"),
        ("POSTGRES_PASSWORD", "change-me-for-local-development"),
        ("SITE_ADDRESS", "localhost"),
        ("PERSONAL_DATA_ENCRYPTION_KEY", "development-only-personal-data-key"),
    ],
)
def test_production_configuration_rejects_known_placeholders(field: str, value: str):
    with pytest.raises(ImproperlyConfigured, match=field):
        validate_runtime_environment(production_environment(**{field: value}))


def test_production_configuration_requires_an_explicit_mode():
    with pytest.raises(ImproperlyConfigured, match="APP_ENV"):
        validate_runtime_environment({})


def test_production_configuration_accepts_non_placeholder_values():
    validate_runtime_environment(production_environment())


def test_mercadopago_oauth_requires_the_complete_server_configuration():
    with pytest.raises(ImproperlyConfigured, match="MERCADOPAGO_OAUTH_CLIENT_SECRET"):
        validate_runtime_environment(
            production_environment(MERCADOPAGO_OAUTH_CLIENT_ID="123456")
        )


def test_mercadopago_oauth_does_not_require_webhook_to_start_authorization():
    validate_runtime_environment(
        production_environment(
            MERCADOPAGO_OAUTH_CLIENT_ID="123456",
            MERCADOPAGO_OAUTH_CLIENT_SECRET="oauth-secret",
        )
    )


def test_mercadopago_oauth_requires_https_redirect_in_production():
    with pytest.raises(ImproperlyConfigured, match="must use HTTPS"):
        validate_runtime_environment(
            production_environment(
                MERCADOPAGO_OAUTH_CLIENT_ID="123456",
                MERCADOPAGO_OAUTH_CLIENT_SECRET="oauth-secret",
                MERCADOPAGO_WEBHOOK_SECRET="webhook-secret",
                MERCADOPAGO_OAUTH_REDIRECT_URI=(
                    "http://shop.example.com/api/v1/payments/mercadopago/oauth/callback/"
                ),
            )
        )


def test_production_settings_pass_django_deploy_checks():
    environment = os.environ | production_environment(
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY=(
            "X9vR2pL7sQ4kN8tB5mC1zH6eW3yU0aF9vR2pL7sQ4kN8tB5mC1zH6eW3"
        )
    )
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_pooled_database_settings_disable_session_bound_connection_state():
    database = database_config(
        {
            "POSTGRES_DB": "storefront",
            "POSTGRES_USER": "storefront_app",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_HOST": "pgbouncer",
            "POSTGRES_PORT": "6432",
        }
    )

    assert database["HOST"] == "pgbouncer"
    assert database["PORT"] == "6432"
    assert database["CONN_MAX_AGE"] == 0
    assert database["DISABLE_SERVER_SIDE_CURSORS"] is True


def test_database_pool_can_be_bypassed_with_one_rollback_switch():
    database = database_config(
        {
            "POSTGRES_DB": "storefront",
            "POSTGRES_USER": "storefront_app",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_HOST": "pgbouncer",
            "POSTGRES_PORT": "6432",
            "POSTGRES_DIRECT_HOST": "postgres",
            "POSTGRES_DIRECT_PORT": "5432",
            "POSTGRES_BYPASS_POOL": "true",
        }
    )

    assert database["HOST"] == "postgres"
    assert database["PORT"] == "5432"
