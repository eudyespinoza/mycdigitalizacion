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
        ("collector_id", "live_mode"),
        ("access_token", "webhook_secret"),
        ("collector_id",),
        ("access_token", "webhook_secret"),
    ),
    "correo_argentino": IntegrationDefinition(
        "Correo Argentino",
        (
            "base_url",
            "customer_id",
            "origin_postal_code",
            "surcharge_type",
            "surcharge_value",
            "free_shipping_threshold",
        ),
        ("username", "password"),
        ("base_url", "customer_id", "origin_postal_code"),
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
    "geolocation": IntegrationDefinition(
        "Geolocalización",
        ("provider", "tile_url", "attribution"),
        (),
        ("provider", "tile_url", "attribution"),
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
    if not complete:
        return "incomplete"
    if configuration.last_test_status == "error":
        return "error"
    return "configured"


def serialize_configuration(provider, configuration=None):
    definition = INTEGRATION_DEFINITIONS[provider]
    secrets = unseal_secret_map(configuration.sealed_secrets) if configuration else {}
    return {
        "provider": provider,
        "label": definition.label,
        "enabled": configuration.enabled if configuration else False,
        "environment": configuration.environment if configuration else "sandbox",
        "status": get_configuration_status(configuration, definition, secrets),
        "public_config": configuration.public_config if configuration else {},
        "secret_fields": {field: bool(secrets.get(field)) for field in definition.secret_fields},
        "version": configuration.version if configuration else 0,
        "updated_at": configuration.updated_at if configuration else None,
        "updated_by": (
            configuration.updated_by.email
            if configuration and configuration.updated_by_id
            else ""
        ),
        "last_test_status": configuration.last_test_status if configuration else "",
        "last_tested_at": configuration.last_tested_at if configuration else None,
        "last_test_message": configuration.last_test_message if configuration else "",
    }


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
