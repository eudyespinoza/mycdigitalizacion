from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

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


class ProviderNotSupported(ProviderError):
    code = "not_supported"


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
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"
        body = None if json is None else __import__("json").dumps(json).encode()
        request_headers = {"Accept": "application/json", **(headers or {})}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ProviderInvalidResponse("La URL del proveedor es inválida")
        connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_type(parsed.hostname, parsed.port, timeout=timeout[0])
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        try:
            connection.connect()
            if connection.sock is not None:
                connection.sock.settimeout(timeout[1])
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            return response.status, json_loads(response.read())
        except TimeoutError as exc:
            raise ProviderTimeout("El proveedor tardó demasiado en responder") from exc
        except HTTPException as exc:
            raise ProviderUnavailable(
                "El proveedor no está disponible",
                diagnostics=f"http_protocol={type(exc).__name__}",
            ) from exc
        except OSError as exc:
            raise ProviderUnavailable("El proveedor no está disponible") from exc
        finally:
            connection.close()


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
                if not isinstance(data, dict | list):
                    raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida")
                return data
            if status in {408, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                continue
            if status in {400, 401, 402, 403, 404, 409, 422}:
                raise ProviderRejected(
                    "El proveedor rechazó la operación", diagnostics=f"http_status={status}"
                )
            raise ProviderUnavailable(
                "El proveedor no está disponible", diagnostics=f"http_status={status}"
            )
        raise ProviderUnavailable("El proveedor no está disponible")
