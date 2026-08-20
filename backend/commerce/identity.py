from __future__ import annotations

from dataclasses import dataclass

from providers import (
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    ProviderRejected,
    UrllibJsonTransport,
)


@dataclass(frozen=True)
class SIDResult:
    status: str
    reference: str
    masked_data: dict[str, str]


class DisabledSIDAdapter:
    def verify(self, *, dni, consent):
        del dni, consent
        raise ProviderNotConfigured("La validación de identidad no está configurada")


class SIDAdapter:
    def __init__(self, *, base_url, token, transport=None):
        if not base_url or not token:
            raise ProviderNotConfigured("La validación de identidad no está configurada")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())

    def verify(self, *, dni, consent):
        if not consent:
            raise ProviderRejected("Se requiere consentimiento para validar la identidad")
        data = self.http.request_json(
            "POST",
            f"{self.base_url}/verify",
            headers={"Authorization": f"Bearer {self.token}"},
            payload={"dni": dni, "consent": True},
            expected=(200, 201),
        )
        status = str(data.get("status", "")).lower()
        if status in {"rejected", "denied", "invalid"}:
            raise ProviderRejected(
                "No pudimos validar la identidad", diagnostics="sid_status=rejected"
            )
        if status not in {"approved", "verified"} or not data.get("reference"):
            raise ProviderInvalidResponse("SID devolvió una respuesta inválida")
        return SIDResult(
            status="approved",
            reference=str(data["reference"]),
            masked_data={
                key: str(data[key])
                for key in ("document_last4", "result_code")
                if data.get(key) is not None
            },
        )
