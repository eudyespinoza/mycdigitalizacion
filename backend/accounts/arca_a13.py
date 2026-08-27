from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from django.core.cache import cache

from providers import (
    ProviderInvalidResponse,
    ProviderNotConfigured,
    ProviderRejected,
    ProviderUnavailable,
)

SERVICE_ID = "ws_sr_padron_a13"
WSAA_TESTING_URL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
WSAA_PRODUCTION_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
A13_TESTING_URL = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13"
A13_PRODUCTION_URL = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13"
SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
WSAA_NAMESPACE = "http://wsaa.view.sua.dvadac.desein.afip.gov"
A13_NAMESPACE = "http://a13.soap.ws.server.puc.sr/"
MAX_XML_BYTES = 2 * 1024 * 1024


class ArcaConfigurationError(ProviderNotConfigured):
    pass


class ArcaValidationError(ProviderRejected):
    pass


class ArcaUnavailableError(ProviderUnavailable):
    pass


class ArcaInvalidResponse(ProviderInvalidResponse):
    pass


@dataclass(frozen=True)
class ArcaA13Settings:
    environment: str
    represented_cuit: str
    certificate_pem: str = ""
    private_key_pem: str = ""
    private_key_passphrase: str = ""
    pfx_base64: str = ""
    pfx_password: str = ""
    wsaa_url: str = ""
    a13_url: str = ""


@dataclass(frozen=True)
class ArcaTicket:
    token: str
    sign: str
    expires_at: datetime


@dataclass(frozen=True)
class ArcaPerson:
    id_persona: str
    numero_documento: str
    estado_clave: str
    nombre: str = ""
    apellido: str = ""
    razon_social: str = ""


class XmlTransport(Protocol):
    def post(
        self,
        url: str,
        body: bytes,
        *,
        headers: dict[str, str],
        timeout: tuple[float, float],
    ) -> tuple[int, bytes]: ...


class RequestsXmlTransport:
    def post(
        self,
        url: str,
        body: bytes,
        *,
        headers: dict[str, str],
        timeout: tuple[float, float],
    ) -> tuple[int, bytes]:
        try:
            response = requests.post(
                url,
                data=body,
                headers=headers,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise ArcaUnavailableError("ARCA tardó demasiado en responder.") from exc
        except requests.RequestException as exc:
            raise ArcaUnavailableError("ARCA no está disponible en este momento.") from exc
        return response.status_code, response.content


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(raw: bytes) -> ElementTree.Element:
    if len(raw) > MAX_XML_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ArcaInvalidResponse("ARCA devolvió una respuesta inválida.")
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ArcaInvalidResponse("ARCA devolvió una respuesta inválida.") from exc


def _first_text(root: ElementTree.Element, name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text:
            return element.text.strip()
    return ""


def _all_text(root: ElementTree.Element, name: str) -> list[str]:
    return [
        element.text.strip()
        for element in root.iter()
        if _local_name(element.tag) == name and element.text and element.text.strip()
    ]


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArcaInvalidResponse("ARCA devolvió una vigencia inválida.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class ArcaA13Client:
    service_id = SERVICE_ID

    def __init__(
        self,
        settings: ArcaA13Settings,
        *,
        transport: XmlTransport | None = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ):
        self.settings = settings
        self.transport = transport or RequestsXmlTransport()
        self.timeout = timeout
        self._credential_cache = None

    @property
    def wsaa_url(self) -> str:
        default = (
            WSAA_PRODUCTION_URL
            if self.settings.environment == "production"
            else WSAA_TESTING_URL
        )
        return self._validated_url(self.settings.wsaa_url or default)

    @property
    def a13_url(self) -> str:
        default = (
            A13_PRODUCTION_URL
            if self.settings.environment == "production"
            else A13_TESTING_URL
        )
        return self._validated_url(self.settings.a13_url or default)

    @staticmethod
    def _validated_url(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ArcaConfigurationError("La URL configurada para ARCA debe usar HTTPS.")
        return value

    def validate_credentials(self) -> str:
        _, certificate = self._load_credentials()
        return certificate.fingerprint(hashes.SHA256()).hex()

    def _load_credentials(self):
        if self._credential_cache is not None:
            return self._credential_cache
        try:
            if self.settings.pfx_base64:
                raw_pfx = base64.b64decode(self.settings.pfx_base64, validate=True)
                password = (
                    self.settings.pfx_password.encode()
                    if self.settings.pfx_password
                    else None
                )
                private_key, certificate, _ = pkcs12.load_key_and_certificates(
                    raw_pfx, password
                )
            elif self.settings.certificate_pem and self.settings.private_key_pem:
                password = (
                    self.settings.private_key_passphrase.encode()
                    if self.settings.private_key_passphrase
                    else None
                )
                private_key = serialization.load_pem_private_key(
                    self.settings.private_key_pem.encode(), password=password
                )
                certificate = x509.load_pem_x509_certificate(
                    self.settings.certificate_pem.encode()
                )
            else:
                raise ValueError("missing credential bundle")
            if private_key is None or certificate is None:
                raise ValueError("incomplete credential bundle")
        except (TypeError, ValueError, base64.binascii.Error) as exc:
            raise ArcaConfigurationError(
                "No pudimos abrir las credenciales de ARCA. Revisá los archivos y contraseñas."
            ) from exc
        self._credential_cache = (private_key, certificate)
        return self._credential_cache

    def _build_tra(self) -> bytes:
        now = datetime.now(UTC)
        root = ElementTree.Element("loginTicketRequest", version="1.0")
        header = ElementTree.SubElement(root, "header")
        ElementTree.SubElement(header, "uniqueId").text = str(
            int(now.timestamp() * 1_000_000)
        )
        ElementTree.SubElement(header, "generationTime").text = (
            now - timedelta(minutes=5)
        ).isoformat()
        ElementTree.SubElement(header, "expirationTime").text = (
            now + timedelta(minutes=10)
        ).isoformat()
        ElementTree.SubElement(root, "service").text = self.service_id
        return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)

    def _signed_tra(self) -> str:
        private_key, certificate = self._load_credentials()
        signed = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(self._build_tra())
            .add_signer(certificate, private_key, hashes.SHA256())
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.Binary],
            )
        )
        return base64.b64encode(signed).decode()

    def _ticket_cache_key(self) -> str:
        fingerprint = self.validate_credentials()
        raw = "|".join(
            (
                self.settings.environment,
                self.settings.represented_cuit,
                fingerprint,
                self.service_id,
            )
        )
        return f"arca:a13:ticket:{hashlib.sha256(raw.encode()).hexdigest()}"

    def _ticket(self) -> ArcaTicket:
        key = self._ticket_cache_key()
        cached = cache.get(key)
        now = datetime.now(UTC)
        if cached:
            expires_at = _parse_datetime(cached["expires_at"])
            if expires_at > now + timedelta(minutes=2):
                return ArcaTicket(cached["token"], cached["sign"], expires_at)

        envelope = self._soap_envelope(
            "loginCms",
            {"in0": self._signed_tra()},
            namespace=WSAA_NAMESPACE,
        )
        root = self._post(self.wsaa_url, envelope)
        serialized_ticket = _first_text(root, "loginCmsReturn")
        if not serialized_ticket:
            raise ArcaInvalidResponse("WSAA devolvió una respuesta inválida.")
        ticket_root = _parse_xml(serialized_ticket.encode())
        token = _first_text(ticket_root, "token")
        sign = _first_text(ticket_root, "sign")
        expiration = _first_text(ticket_root, "expirationTime")
        if not token or not sign or not expiration:
            raise ArcaInvalidResponse("WSAA devolvió una respuesta inválida.")
        expires_at = _parse_datetime(expiration)
        if expires_at <= now + timedelta(minutes=2):
            raise ArcaInvalidResponse("WSAA devolvió un ticket vencido.")
        timeout = max(1, int((expires_at - now - timedelta(minutes=2)).total_seconds()))
        cache.set(
            key,
            {"token": token, "sign": sign, "expires_at": expires_at.isoformat()},
            timeout=timeout,
        )
        return ArcaTicket(token, sign, expires_at)

    @staticmethod
    def _soap_envelope(
        operation: str,
        params: dict[str, str],
        *,
        namespace: str = A13_NAMESPACE,
    ) -> bytes:
        envelope = ElementTree.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
        ElementTree.SubElement(envelope, f"{{{SOAP_NAMESPACE}}}Header")
        body = ElementTree.SubElement(envelope, f"{{{SOAP_NAMESPACE}}}Body")
        request = ElementTree.SubElement(body, f"{{{namespace}}}{operation}")
        for name, value in params.items():
            ElementTree.SubElement(request, name).text = value
        return ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)

    def _post(
        self,
        url: str,
        body: bytes,
    ) -> ElementTree.Element:
        try:
            status, raw = self.transport.post(
                url,
                body,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "",
                    "Accept": "text/xml",
                },
                timeout=self.timeout,
            )
        except (ArcaUnavailableError, ArcaInvalidResponse):
            raise
        except Exception as exc:
            raise ArcaUnavailableError("ARCA no está disponible en este momento.") from exc
        if status >= 500:
            raise ArcaUnavailableError("ARCA no está disponible en este momento.")
        root = _parse_xml(raw)
        if any(_local_name(element.tag) == "Fault" for element in root.iter()):
            raise ArcaValidationError("ARCA rechazó la consulta. Revisá la configuración.")
        if status not in {200, 201}:
            raise ArcaValidationError("ARCA rechazó la consulta.")
        return root

    def _a13_call(self, operation: str, params: dict[str, str]) -> ElementTree.Element:
        ticket = self._ticket()
        auth = {
            "token": ticket.token,
            "sign": ticket.sign,
            "cuitRepresentada": self.settings.represented_cuit,
        }
        return self._post(
            self.a13_url,
            self._soap_envelope(operation, {**auth, **params}),
        )

    def dummy(self) -> bool:
        self._ticket()
        root = self._post(
            self.a13_url,
            self._soap_envelope("dummy", {}),
        )
        statuses = [
            _first_text(root, name).upper()
            for name in ("appserver", "authserver", "dbserver")
        ]
        return bool(statuses) and all(status == "OK" for status in statuses)

    def get_id_persona_list_by_documento(self, documento: str) -> list[str]:
        root = self._a13_call(
            "getIdPersonaListByDocumento", {"documento": documento}
        )
        return list(dict.fromkeys(_all_text(root, "idPersona")))

    def get_persona(self, id_persona: str) -> ArcaPerson:
        root = self._a13_call("getPersona", {"idPersona": id_persona})
        returned_id = _first_text(root, "idPersona")
        if not returned_id:
            raise ArcaInvalidResponse("ARCA devolvió una respuesta inválida.")
        return ArcaPerson(
            id_persona=returned_id,
            numero_documento=_first_text(root, "numeroDocumento"),
            estado_clave=_first_text(root, "estadoClave"),
            nombre=_first_text(root, "nombre"),
            apellido=_first_text(root, "apellido"),
            razon_social=_first_text(root, "razonSocial"),
        )
