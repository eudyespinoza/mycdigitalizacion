from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError

from accounts.arca_a13 import (
    ArcaA13Client,
    ArcaA13Settings,
    ArcaConfigurationError,
    ArcaInvalidResponse,
    ArcaUnavailableError,
    ArcaValidationError,
)
from accounts.models import normalize_cuit
from backoffice.integrations import resolved_configuration


class FiscalIdentityError(ValueError):
    pass


def only_digits(value: str) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


def get_arca_a13_client() -> ArcaA13Client | None:
    stored = resolved_configuration("arca_a13")
    if stored is None or not stored["enabled"]:
        return None
    public = stored["public_config"]
    secrets = stored["secrets"]
    try:
        represented_cuit = normalize_cuit(str(public.get("represented_cuit", "")))
    except DjangoValidationError:
        return None
    has_pem = bool(secrets.get("certificate_pem") and secrets.get("private_key_pem"))
    has_pfx = bool(secrets.get("pfx_base64"))
    if not has_pem and not has_pfx:
        return None
    return ArcaA13Client(
        ArcaA13Settings(
            environment=stored["environment"],
            represented_cuit=represented_cuit,
            certificate_pem=str(secrets.get("certificate_pem", "")),
            private_key_pem=str(secrets.get("private_key_pem", "")),
            private_key_passphrase=str(secrets.get("private_key_passphrase", "")),
            pfx_base64=str(secrets.get("pfx_base64", "")),
            pfx_password=str(secrets.get("pfx_password", "")),
            wsaa_url=str(public.get("wsaa_url", "")),
            a13_url=str(public.get("a13_url", "")),
        )
    )


def _normalize_cuit(value: str) -> str:
    try:
        return normalize_cuit(value)
    except DjangoValidationError as exc:
        raise FiscalIdentityError("El CUIT ingresado no es válido.") from exc


def _same_document(left: str, right: str) -> bool:
    left_digits = only_digits(left).lstrip("0")
    right_digits = only_digits(right).lstrip("0")
    return bool(left_digits and right_digits and left_digits == right_digits)


def resolve_fiscal_identifier(raw_identifier: str) -> str:
    digits = only_digits(raw_identifier)
    if len(digits) == 11:
        cuit = _normalize_cuit(digits)
        source_dni = ""
    elif len(digits) in {7, 8}:
        source_dni = digits
        cuit = ""
    else:
        raise FiscalIdentityError(
            "Ingresá un DNI de 7 u 8 dígitos o un CUIT de 11 dígitos."
        )

    adapter = get_arca_a13_client()
    if adapter is None:
        if source_dni:
            raise FiscalIdentityError(
                "La validación ARCA no está configurada. Ingresá el CUIT completo de 11 dígitos."
            )
        return cuit

    try:
        if source_dni:
            candidates = list(
                dict.fromkeys(
                    adapter.get_id_persona_list_by_documento(source_dni)
                )
            )
            if not candidates:
                raise FiscalIdentityError(
                    "ARCA no encontró un CUIT asociado al DNI informado."
                )
            if len(candidates) > 1:
                raise FiscalIdentityError(
                    "ARCA encontró más de un CUIT para el DNI informado. Ingresá el CUIT completo."
                )
            cuit = _normalize_cuit(candidates[0])

        person = adapter.get_persona(cuit)
    except (ArcaConfigurationError, ArcaInvalidResponse, ArcaUnavailableError):
        raise
    except ArcaValidationError as exc:
        raise FiscalIdentityError("ARCA no pudo validar los datos ingresados.") from exc

    if only_digits(person.id_persona) != cuit:
        raise FiscalIdentityError("ARCA devolvió una identidad fiscal diferente.")
    if person.estado_clave.strip().upper() != "ACTIVO":
        raise FiscalIdentityError("El CUIT informado no está activo en ARCA.")
    if source_dni and not _same_document(person.numero_documento, source_dni):
        raise FiscalIdentityError(
            "El CUIT encontrado no coincide con el documento informado."
        )
    return cuit
