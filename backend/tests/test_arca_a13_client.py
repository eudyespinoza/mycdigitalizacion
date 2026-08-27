import base64
import html
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core.cache import cache

from accounts.arca_a13 import (
    A13_PRODUCTION_URL,
    A13_TESTING_URL,
    WSAA_PRODUCTION_URL,
    WSAA_TESTING_URL,
    ArcaA13Client,
    ArcaA13Settings,
    ArcaConfigurationError,
    ArcaInvalidResponse,
)


class FakeXmlTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, body, *, headers, timeout):
        self.requests.append(
            {"url": url, "body": body.decode(), "headers": headers, "timeout": timeout}
        )
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def clear_ticket_cache():
    cache.clear()


@pytest.fixture
def certificate_bundle():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ARCA test")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pfx = pkcs12.serialize_key_and_certificates(
        b"arca-test",
        key,
        certificate,
        None,
        serialization.BestAvailableEncryption(b"pfx-password"),
    )
    return certificate_pem, key_pem, base64.b64encode(pfx).decode()


def wsaa_response():
    expiration = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    ticket = (
        "<loginTicketResponse><header>"
        f"<expirationTime>{expiration}</expirationTime>"
        "</header><credentials><token>token-value</token>"
        "<sign>sign-value</sign></credentials></loginTicketResponse>"
    )
    return (
        "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
        "<soap:Body><loginCmsResponse><loginCmsReturn>"
        f"{html.escape(ticket)}"
        "</loginCmsReturn></loginCmsResponse></soap:Body></soap:Envelope>"
    ).encode()


def soap_response(body):
    return (
        "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
        f"<soap:Body>{body}</soap:Body></soap:Envelope>"
    ).encode()


def pem_settings(certificate_bundle, **overrides):
    certificate_pem, key_pem, _ = certificate_bundle
    values = {
        "environment": "sandbox",
        "represented_cuit": "20123456786",
        "certificate_pem": certificate_pem,
        "private_key_pem": key_pem,
    }
    values.update(overrides)
    return ArcaA13Settings(**values)


def test_dni_resolution_authenticates_with_wsaa_and_calls_a13(certificate_bundle):
    transport = FakeXmlTransport(
        (200, wsaa_response()),
        (
            200,
            soap_response(
                "<getIdPersonaListByDocumentoResponse><return>"
                "<idPersona>20123456786</idPersona>"
                "</return></getIdPersonaListByDocumentoResponse>"
            ),
        ),
        (
            200,
            soap_response(
                "<getIdPersonaListByDocumentoResponse><return>"
                "<idPersona>20123456786</idPersona>"
                "</return></getIdPersonaListByDocumentoResponse>"
            ),
        ),
    )
    client = ArcaA13Client(pem_settings(certificate_bundle), transport=transport)

    assert client.get_id_persona_list_by_documento("12345678") == ["20123456786"]
    assert client.get_id_persona_list_by_documento("12345678") == ["20123456786"]
    assert client.service_id == "ws_sr_padron_a13"
    assert transport.requests[0]["url"] == WSAA_TESTING_URL
    assert "loginCms" in transport.requests[0]["body"]
    assert transport.requests[1]["url"] == A13_TESTING_URL
    assert "getIdPersonaListByDocumento" in transport.requests[1]["body"]
    assert "12345678" in transport.requests[1]["body"]
    assert "20123456786" in transport.requests[1]["body"]
    assert sum("loginCms" in request["body"] for request in transport.requests) == 1


def test_full_cuit_calls_get_persona_without_document_resolution(certificate_bundle):
    transport = FakeXmlTransport(
        (200, wsaa_response()),
        (
            200,
            soap_response(
                "<getPersonaResponse><return>"
                "<idPersona>20123456786</idPersona>"
                "<numeroDocumento>12345678</numeroDocumento>"
                "<estadoClave>ACTIVO</estadoClave><nombre>Eva</nombre>"
                "<apellido>Prueba</apellido>"
                "</return></getPersonaResponse>"
            ),
        ),
    )
    client = ArcaA13Client(pem_settings(certificate_bundle), transport=transport)

    person = client.get_persona("20123456786")

    assert person.id_persona == "20123456786"
    assert person.numero_documento == "12345678"
    assert person.estado_clave == "ACTIVO"
    assert person.nombre == "Eva"
    bodies = " ".join(request["body"] for request in transport.requests)
    assert "getPersona" in bodies
    assert "getIdPersonaListByDocumento" not in bodies


def test_pfx_credentials_and_production_endpoints_support_dummy(certificate_bundle):
    _, _, pfx_base64 = certificate_bundle
    transport = FakeXmlTransport(
        (200, wsaa_response()),
        (
            200,
            soap_response(
                "<dummyResponse><return><appserver>OK</appserver>"
                "<authserver>OK</authserver><dbserver>OK</dbserver></return></dummyResponse>"
            ),
        ),
    )
    client = ArcaA13Client(
        ArcaA13Settings(
            environment="production",
            represented_cuit="20123456786",
            pfx_base64=pfx_base64,
            pfx_password="pfx-password",
        ),
        transport=transport,
    )

    assert client.dummy() is True
    assert transport.requests[0]["url"] == WSAA_PRODUCTION_URL
    assert transport.requests[1]["url"] == A13_PRODUCTION_URL


def test_invalid_credentials_and_xml_return_safe_errors(certificate_bundle):
    with pytest.raises(ArcaConfigurationError, match="credenciales") as invalid:
        ArcaA13Client(
            ArcaA13Settings(
                environment="sandbox",
                represented_cuit="20123456786",
                certificate_pem="SECRET-CERTIFICATE",
                private_key_pem="SECRET-PRIVATE-KEY",
            )
        ).validate_credentials()
    assert "SECRET" not in str(invalid.value)

    transport = FakeXmlTransport((200, b"not xml"))
    client = ArcaA13Client(pem_settings(certificate_bundle), transport=transport)
    with pytest.raises(ArcaInvalidResponse, match="respuesta inválida"):
        client.get_persona("20123456786")
