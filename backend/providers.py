from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (3.0, 10.0)


class ProviderError(RuntimeError):
    code = "provider_error"

    def __init__(self, message: str, *, diagnostics: str = ""):
        super().__init__(message)
        self.diagnostics = diagnostics


class ProviderUnavailable(ProviderError):
    code = "unavailable"


class ProviderTimeout(ProviderError):
    code = "timeout"


class ProviderInvalidResponse(ProviderError):
    code = "invalid_response"


class ProviderRejected(ProviderError):
    code = "rejected"


class ProviderNotConfigured(ProviderError):
    code = "not_configured"


class JsonTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> tuple[int, Any]: ...


class UrllibJsonTransport:
    """Small JSON transport. Adapters receive it by injection for deterministic tests."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> tuple[int, Any]:
        if params:
            url = f"{url}?{urlencode(params)}"
        body = None if json is None else __import__("json").dumps(json).encode()
        request_headers = {"Accept": "application/json", **(headers or {})}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=body, method=method, headers=request_headers)
        try:
            # urllib exposes a single socket timeout; the adapter contract still carries
            # explicit connect/read values for richer injected transports.
            with urlopen(request, timeout=max(timeout)) as response:  # noqa: S310
                raw = response.read()
                return response.status, json_loads(raw)
        except HTTPError as exc:
            return exc.code, json_loads(exc.read())
        except TimeoutError as exc:
            raise ProviderTimeout("El proveedor tardó demasiado en responder") from exc
        except URLError as exc:
            raise ProviderUnavailable("El proveedor no está disponible") from exc


def json_loads(raw: bytes) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida") from exc


@dataclass
class ProviderHttpClient:
    transport: JsonTransport
    retries: int = 2
    timeout: tuple[float, float] = DEFAULT_TIMEOUT

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotent: bool = False,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        attempts = 1 + (self.retries if method.upper() == "GET" or idempotent else 0)
        for attempt in range(attempts):
            try:
                status, data = self.transport.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                    timeout=self.timeout,
                )
            except (ProviderTimeout, ProviderUnavailable):
                if attempt + 1 < attempts:
                    continue
                raise
            if status in expected:
                if not isinstance(data, (dict, list)):
                    raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida")
                return data
            if status in {408, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                continue
            if status in {401, 403, 404, 409, 422}:
                raise ProviderRejected(
                    "El proveedor rechazó la operación", diagnostics=f"http_status={status}"
                )
            raise ProviderUnavailable(
                "El proveedor no está disponible", diagnostics=f"http_status={status}"
            )
        raise ProviderUnavailable("El proveedor no está disponible")
