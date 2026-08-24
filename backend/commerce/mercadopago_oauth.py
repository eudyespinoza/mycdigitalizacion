from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from backoffice.models import IntegrationConfiguration, ManagementAuditEvent
from backoffice.secrets import seal_secret_map, unseal_secret_map
from providers import ProviderInvalidResponse, ProviderNotConfigured, ProviderUnavailable

OAUTH_STATE_TTL_SECONDS = 600
OAUTH_REFRESH_WINDOW = timedelta(minutes=5)


class MercadoPagoOAuthError(RuntimeError):
    code = "mercadopago_oauth_error"


class MercadoPagoOAuthNotConfigured(MercadoPagoOAuthError):
    code = "mercadopago_oauth_not_configured"


class MercadoPagoOAuthStateError(MercadoPagoOAuthError):
    code = "mercadopago_oauth_state_invalid"


@dataclass(frozen=True)
class AuthorizationState:
    actor_id: int
    code_verifier: str


@dataclass(frozen=True)
class OAuthApplicationConfiguration:
    client_id: str
    client_secret: str
    webhook_secret: str


TokenRequest = Callable[[dict[str, str]], dict[str, Any]]


def oauth_callback_url() -> str:
    return settings.MERCADOPAGO_OAUTH_REDIRECT_URI


def oauth_application_configuration(
    configuration: IntegrationConfiguration | None = None,
) -> OAuthApplicationConfiguration:
    if configuration is None:
        configuration = IntegrationConfiguration.objects.filter(
            provider="mercadopago"
        ).first()
    public_config = configuration.public_config if configuration else {}
    stored_secrets = (
        unseal_secret_map(configuration.sealed_secrets) if configuration else {}
    )
    return OAuthApplicationConfiguration(
        client_id=str(
            public_config.get("oauth_client_id")
            or settings.MERCADOPAGO_OAUTH_CLIENT_ID
            or ""
        ).strip(),
        client_secret=str(
            stored_secrets.get("oauth_client_secret")
            or settings.MERCADOPAGO_OAUTH_CLIENT_SECRET
            or ""
        ).strip(),
        webhook_secret=str(
            stored_secrets.get("webhook_secret")
            or settings.MERCADOPAGO_WEBHOOK_SECRET
            or ""
        ).strip(),
    )


def oauth_is_ready(configuration: IntegrationConfiguration | None = None) -> bool:
    application = oauth_application_configuration(configuration)
    return all(
        str(value).strip()
        for value in (
            application.client_id,
            application.client_secret,
            settings.MERCADOPAGO_OAUTH_REDIRECT_URI,
        )
    )


def webhook_is_ready(configuration: IntegrationConfiguration | None = None) -> bool:
    return bool(oauth_application_configuration(configuration).webhook_secret)


def _state_digest(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _pending_key(state: str) -> str:
    return f"mercadopago:oauth:pending:{_state_digest(state)}"


def _used_key(state: str) -> str:
    return f"mercadopago:oauth:used:{_state_digest(state)}"


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_authorization_session(actor_id: int) -> str:
    application = oauth_application_configuration()
    if not oauth_is_ready():
        raise MercadoPagoOAuthNotConfigured(
            "Mercado Pago todavía no está preparado para conectar una cuenta."
        )
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    cache.set(
        _pending_key(state),
        {"actor_id": int(actor_id), "code_verifier": code_verifier},
        timeout=OAUTH_STATE_TTL_SECONDS,
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": application.client_id,
            "redirect_uri": oauth_callback_url(),
            "state": state,
            "code_challenge": _code_challenge(code_verifier),
            "code_challenge_method": "S256",
            "platform_id": "mp",
        }
    )
    return f"{settings.MERCADOPAGO_OAUTH_AUTH_URL}?{query}"


def consume_authorization_state(state: str) -> AuthorizationState:
    normalized = str(state or "").strip()
    if not normalized or not cache.add(
        _used_key(normalized), True, timeout=OAUTH_STATE_TTL_SECONDS
    ):
        raise MercadoPagoOAuthStateError(
            "La autorización venció o ya fue utilizada. Volvé a iniciar la conexión."
        )
    payload = cache.get(_pending_key(normalized))
    cache.delete(_pending_key(normalized))
    if not isinstance(payload, dict):
        raise MercadoPagoOAuthStateError(
            "La autorización venció o ya fue utilizada. Volvé a iniciar la conexión."
        )
    actor_id = payload.get("actor_id")
    code_verifier = payload.get("code_verifier")
    if not isinstance(actor_id, int) or not isinstance(code_verifier, str):
        raise MercadoPagoOAuthStateError("La autorización recibida no es válida.")
    if not 43 <= len(code_verifier) <= 128:
        raise MercadoPagoOAuthStateError("La autorización recibida no es válida.")
    return AuthorizationState(actor_id=actor_id, code_verifier=code_verifier)


def _default_token_request(payload: dict[str, str]) -> dict[str, Any]:
    token_url = settings.MERCADOPAGO_OAUTH_TOKEN_URL
    parsed = urlsplit(token_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ProviderNotConfigured("La URL OAuth de Mercado Pago no es segura.")
    body = urlencode(payload).encode("utf-8")
    request = Request(
        token_url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS URL
            raw = response.read()
    except HTTPError as exc:
        raise ProviderUnavailable(
            "Mercado Pago rechazó la autorización.",
            diagnostics=f"http_status={exc.code}",
        ) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise ProviderUnavailable("Mercado Pago no está disponible.") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderInvalidResponse(
            "Mercado Pago devolvió una autorización inválida."
        ) from exc
    if not isinstance(decoded, dict):
        raise ProviderInvalidResponse("Mercado Pago devolvió una autorización inválida.")
    return decoded


def exchange_authorization_code(
    code: str,
    code_verifier: str,
    *,
    token_request: TokenRequest | None = None,
) -> dict[str, Any]:
    application = oauth_application_configuration()
    if not oauth_is_ready():
        raise MercadoPagoOAuthNotConfigured(
            "Mercado Pago todavía no está preparado para conectar una cuenta."
        )
    return (token_request or _default_token_request)(
        {
            "client_id": application.client_id,
            "client_secret": application.client_secret,
            "grant_type": "authorization_code",
            "code": str(code),
            "redirect_uri": oauth_callback_url(),
            "code_verifier": code_verifier,
        }
    )


def _normalize_token_payload(
    payload: dict[str, Any],
    *,
    existing_public: dict[str, Any] | None = None,
    existing_secrets: dict[str, str] | None = None,
) -> dict[str, Any]:
    existing_public = existing_public or {}
    existing_secrets = existing_secrets or {}
    access_token = str(payload.get("access_token") or "").strip()
    refresh_token = str(
        payload.get("refresh_token") or existing_secrets.get("refresh_token") or ""
    ).strip()
    user_id = str(payload.get("user_id") or existing_public.get("collector_id") or "").strip()
    try:
        expires_in = int(payload.get("expires_in") or 0)
    except (TypeError, ValueError) as exc:
        raise ProviderInvalidResponse(
            "Mercado Pago no devolvió la vigencia de la autorización."
        ) from exc
    if not access_token or not refresh_token or not user_id or expires_in <= 0:
        raise ProviderInvalidResponse(
            "Mercado Pago no devolvió todas las credenciales necesarias."
        )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "collector_id": user_id,
        "live_mode": bool(payload.get("live_mode", existing_public.get("live_mode", False))),
        "expires_in": expires_in,
    }


@transaction.atomic
def store_oauth_credentials(
    payload: dict[str, Any],
    *,
    actor=None,
    audit_action: str = "integration.oauth_connected",
) -> IntegrationConfiguration:
    configuration = (
        IntegrationConfiguration.objects.select_for_update()
        .filter(provider="mercadopago")
        .first()
    )
    created = configuration is None
    if configuration is None:
        configuration = IntegrationConfiguration(provider="mercadopago")
    existing_secrets = unseal_secret_map(configuration.sealed_secrets)
    normalized = _normalize_token_payload(
        payload,
        existing_public=configuration.public_config,
        existing_secrets=existing_secrets,
    )
    now = timezone.now()
    connected_at = configuration.public_config.get("oauth_connected_at") or now.isoformat()
    configuration.enabled = True
    configuration.environment = "production" if normalized["live_mode"] else "sandbox"
    configuration.public_config = {
        **configuration.public_config,
        "collector_id": normalized["collector_id"],
        "live_mode": normalized["live_mode"],
        "oauth_connected_at": connected_at,
        "oauth_reconnect_required": False,
        "token_expires_at": (now + timedelta(seconds=normalized["expires_in"])).isoformat(),
    }
    stored_secrets = {
        **existing_secrets,
        "access_token": normalized["access_token"],
        "refresh_token": normalized["refresh_token"],
    }
    if not stored_secrets.get("webhook_secret") and settings.MERCADOPAGO_WEBHOOK_SECRET:
        stored_secrets["webhook_secret"] = settings.MERCADOPAGO_WEBHOOK_SECRET
    configuration.sealed_secrets = seal_secret_map(stored_secrets)
    if actor is not None:
        configuration.updated_by = actor
    configuration.version = 1 if created else configuration.version + 1
    configuration.last_test_status = "success"
    configuration.last_tested_at = now
    configuration.last_test_message = "Cuenta de Mercado Pago conectada."
    configuration.full_clean()
    configuration.save()
    if actor is not None:
        ManagementAuditEvent.objects.create(
            actor=actor,
            action=audit_action,
            resource="integration",
            object_reference="mercadopago",
            metadata={"collector_id": normalized["collector_id"]},
        )
    return configuration


def _mark_reconnect_required(configuration: IntegrationConfiguration) -> None:
    public_config = dict(configuration.public_config)
    public_config["oauth_reconnect_required"] = True
    configuration.public_config = public_config
    configuration.last_test_status = "error"
    configuration.last_tested_at = timezone.now()
    configuration.last_test_message = "La autorización venció. Volvé a conectar Mercado Pago."
    configuration.save(
        update_fields=(
            "public_config",
            "last_test_status",
            "last_tested_at",
            "last_test_message",
            "updated_at",
        )
    )


def resolve_oauth_access_token(*, token_request: TokenRequest | None = None) -> str:
    configuration = IntegrationConfiguration.objects.filter(provider="mercadopago").first()
    if configuration is None or not configuration.enabled:
        raise ProviderNotConfigured("Mercado Pago no está conectado.")
    stored_secrets = unseal_secret_map(configuration.sealed_secrets)
    access_token = stored_secrets.get("access_token", "")
    refresh_token = stored_secrets.get("refresh_token", "")
    expires_at = parse_datetime(str(configuration.public_config.get("token_expires_at", "")))
    if access_token and (expires_at is None or expires_at > timezone.now() + OAUTH_REFRESH_WINDOW):
        return access_token
    application = oauth_application_configuration(configuration)
    if not refresh_token or not oauth_is_ready(configuration):
        _mark_reconnect_required(configuration)
        raise ProviderNotConfigured("Mercado Pago necesita volver a conectarse.")
    try:
        payload = (token_request or _default_token_request)(
            {
                "client_id": application.client_id,
                "client_secret": application.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "redirect_uri": oauth_callback_url(),
            }
        )
        refreshed = store_oauth_credentials(payload, audit_action="integration.oauth_refreshed")
    except (ProviderInvalidResponse, ProviderUnavailable, MercadoPagoOAuthError):
        _mark_reconnect_required(configuration)
        raise
    return unseal_secret_map(refreshed.sealed_secrets)["access_token"]


@transaction.atomic
def disconnect_mercadopago(*, actor) -> IntegrationConfiguration:
    configuration = (
        IntegrationConfiguration.objects.select_for_update()
        .filter(provider="mercadopago")
        .first()
    )
    if configuration is None:
        configuration = IntegrationConfiguration(provider="mercadopago")
    existing_secrets = unseal_secret_map(configuration.sealed_secrets)
    configuration.enabled = False
    configuration.public_config = {
        "oauth_client_id": configuration.public_config.get("oauth_client_id", ""),
        "collector_id": "",
        "live_mode": False,
        "oauth_connected_at": None,
        "oauth_reconnect_required": False,
        "token_expires_at": None,
    }
    configuration.sealed_secrets = seal_secret_map(
        {
            key: value
            for key, value in existing_secrets.items()
            if key in {"oauth_client_secret", "webhook_secret"} and value
        }
    )
    configuration.updated_by = actor
    configuration.version = max(configuration.version, 0) + 1
    configuration.last_test_status = ""
    configuration.last_tested_at = timezone.now()
    configuration.last_test_message = "Mercado Pago fue desconectado."
    configuration.full_clean()
    configuration.save()
    ManagementAuditEvent.objects.create(
        actor=actor,
        action="integration.oauth_disconnected",
        resource="integration",
        object_reference="mercadopago",
        metadata={},
    )
    return configuration
