from dataclasses import dataclass

from backoffice.secrets import unseal_secret_map


@dataclass(frozen=True)
class IntegrationDefinition:
    label: str
    public_fields: tuple[str, ...]
    secret_fields: tuple[str, ...]
    required_public: tuple[str, ...]
    required_secrets: tuple[str, ...]


INTEGRATION_DEFINITIONS = {
    "mercadopago": IntegrationDefinition(
        "Mercado Pago",
        ("collector_id", "live_mode", "oauth_client_id"),
        (
            "access_token",
            "refresh_token",
            "oauth_client_secret",
            "webhook_secret",
        ),
        ("collector_id",),
        ("access_token", "webhook_secret"),
    ),
    "correo_argentino": IntegrationDefinition(
        "API MiCorreo",
        (
            "base_url",
            "customer_id",
            "origin_postal_code",
            "surcharge_type",
            "surcharge_value",
            "free_shipping_threshold",
        ),
        ("username", "password"),
        ("customer_id", "origin_postal_code"),
        ("username", "password"),
    ),
    "andreani": IntegrationDefinition(
        "Andreani",
        (
            "base_url",
            "customer_id",
            "contract",
            "origin_postal_code",
            "origin_street",
            "origin_number",
            "origin_city",
            "origin_province",
            "sender_name",
            "sender_email",
            "sender_phone",
            "sender_document_type",
            "sender_document_number",
            "surcharge_type",
            "surcharge_value",
            "free_shipping_threshold",
        ),
        ("username", "password"),
        (
            "customer_id",
            "contract",
            "origin_postal_code",
            "origin_street",
            "origin_number",
            "origin_city",
            "sender_name",
            "sender_email",
            "sender_phone",
            "sender_document_type",
            "sender_document_number",
        ),
        ("username", "password"),
    ),
    "sid_renaper": IntegrationDefinition(
        "SID RENAPER",
        ("base_url",),
        ("access_token",),
        ("base_url",),
        ("access_token",),
    ),
    "smtp": IntegrationDefinition(
        "Correo transaccional",
        ("host", "port", "use_tls", "from_email"),
        ("username", "password"),
        ("host", "port", "from_email"),
        ("username", "password"),
    ),
    "google_identity": IntegrationDefinition(
        "Acceso con Google",
        ("client_id",),
        (),
        ("client_id",),
        (),
    ),
    "geolocation": IntegrationDefinition(
        "Mapas",
        ("provider", "google_maps_map_id"),
        ("google_maps_browser_key",),
        ("provider",),
        (),
    ),
    "backups": IntegrationDefinition(
        "Copias externas",
        ("repository", "region", "retention_days"),
        ("access_key", "secret_key", "repository_password"),
        ("repository", "region", "retention_days"),
        ("access_key", "secret_key", "repository_password"),
    ),
}


def get_definition(provider):
    return INTEGRATION_DEFINITIONS.get(provider)


def get_configuration_status(configuration, definition, secrets=None):
    if configuration is None or not configuration.enabled:
        return "disabled" if configuration is not None else "incomplete"
    secret_values = (
        secrets
        if secrets is not None
        else unseal_secret_map(configuration.sealed_secrets)
    )
    complete = all(
        configuration.public_config.get(field) not in (None, "")
        for field in definition.required_public
    )
    complete = complete and all(secret_values.get(field) for field in definition.required_secrets)
    if (
        definition is INTEGRATION_DEFINITIONS["geolocation"]
        and configuration.public_config.get("provider") == "google_maps"
    ):
        complete = complete and bool(secret_values.get("google_maps_browser_key"))
    if not complete:
        return "incomplete"
    if configuration.last_test_status == "error":
        return "error"
    return "configured"


def serialize_configuration(provider, configuration=None):
    definition = INTEGRATION_DEFINITIONS[provider]
    secrets = unseal_secret_map(configuration.sealed_secrets) if configuration else {}
    serialized = {
        "provider": provider,
        "label": definition.label,
        "enabled": configuration.enabled if configuration else False,
        "environment": configuration.environment if configuration else "sandbox",
        "status": get_configuration_status(configuration, definition, secrets),
        "public_config": configuration.public_config if configuration else {},
        "secret_fields": {field: bool(secrets.get(field)) for field in definition.secret_fields},
        "version": configuration.version if configuration else 0,
        "updated_at": (
            configuration.updated_at.isoformat()
            if configuration and configuration.updated_at
            else None
        ),
        "updated_by": (
            configuration.updated_by.email
            if configuration and configuration.updated_by_id
            else ""
        ),
        "last_test_status": configuration.last_test_status if configuration else "",
        "last_tested_at": (
            configuration.last_tested_at.isoformat()
            if configuration and configuration.last_tested_at
            else None
        ),
        "last_test_message": configuration.last_test_message if configuration else "",
    }
    if provider == "mercadopago":
        from commerce.mercadopago_oauth import (
            oauth_application_configuration,
            oauth_callback_url,
            oauth_is_ready,
            webhook_is_ready,
        )

        application = oauth_application_configuration(configuration)
        oauth_ready = oauth_is_ready(configuration)
        serialized["public_config"] = {
            **serialized["public_config"],
            "oauth_client_id": application.client_id,
        }
        serialized["secret_fields"]["oauth_client_secret"] = bool(
            application.client_secret
        )
        serialized["secret_fields"]["webhook_secret"] = bool(
            application.webhook_secret
        )

        connected = bool(
            configuration
            and configuration.enabled
            and secrets.get("access_token")
            and (
                secrets.get("refresh_token")
                or configuration.public_config.get("oauth_grant_type")
                == "client_credentials"
            )
        )
        reconnect_required = bool(
            configuration
            and configuration.public_config.get("oauth_reconnect_required", False)
        )
        if connected and reconnect_required:
            oauth_status = "reconnect_required"
        elif connected:
            oauth_status = "connected"
        elif not oauth_ready:
            oauth_status = "not_ready"
        else:
            oauth_status = "disconnected"
        serialized.update(
            {
                "oauth_ready": oauth_ready,
                "oauth_status": oauth_status,
                "webhook_ready": webhook_is_ready(configuration),
                "oauth_callback_url": oauth_callback_url(),
                "connected_account_id": (
                    str(configuration.public_config.get("collector_id") or "")
                    if configuration
                    else ""
                ),
                "oauth_connected_at": (
                    configuration.public_config.get("oauth_connected_at")
                    if configuration
                    else None
                ),
            }
        )
    return serialized


def resolved_configuration(provider):
    from django.db import DatabaseError

    from backoffice.models import IntegrationConfiguration

    try:
        configuration = IntegrationConfiguration.objects.filter(provider=provider).first()
    except DatabaseError:
        return None
    if configuration is None:
        return None
    return {
        "enabled": configuration.enabled,
        "environment": configuration.environment,
        "public_config": configuration.public_config,
        "secrets": unseal_secret_map(configuration.sealed_secrets),
    }
