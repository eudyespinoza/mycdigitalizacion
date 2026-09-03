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


class ProviderAuthenticationError(ProviderError):
    code = "authentication_failed"


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
    ) -> tuple[int, Any] | tuple[int, dict[str, str], Any]: ...


@dataclass(frozen=True)
class ProviderHttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


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
        response = self.request_response(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
            timeout=timeout,
        )
        return response.status, json_loads(response.body)

    def request_response(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> ProviderHttpResponse:
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
            response_headers = getattr(response, "getheaders", lambda: ())()
            return ProviderHttpResponse(
                status=response.status,
                headers={str(key).lower(): str(value) for key, value in response_headers},
                body=response.read(),
            )
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
        return self.request_json_response(
            method,
            url,
            headers=headers,
            payload=payload,
            params=params,
            idempotent=idempotent,
            expected=expected,
        ).body

    def request_json_response(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotent: bool = False,
        expected: tuple[int, ...] = (200,),
    ) -> ProviderHttpResponse:
        response = self._request_response(
            method,
            url,
            headers=headers,
            payload=payload,
            params=params,
            idempotent=idempotent,
            expected=expected,
        )
        data = json_loads(response.body) if isinstance(response.body, bytes) else response.body
        if not isinstance(data, dict | list):
            raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida")
        return ProviderHttpResponse(response.status, response.headers, data)

    def request_bytes(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        idempotent: bool = False,
        expected: tuple[int, ...] = (200,),
    ) -> bytes:
        response = self._request_response(
            method,
            url,
            headers=headers,
            params=params,
            idempotent=idempotent,
            expected=expected,
        )
        if not isinstance(response.body, bytes):
            raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida")
        return response.body

    def _request_response(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotent: bool = False,
        expected: tuple[int, ...] = (200,),
    ) -> ProviderHttpResponse:
        attempts = 1 + (self.retries if method.upper() == "GET" or idempotent else 0)
        for attempt in range(attempts):
            try:
                raw_response = self._send(
                    method, url, headers=headers, payload=payload, params=params
                )
            except (ProviderTimeout, ProviderUnavailable):
                if attempt + 1 < attempts:
                    continue
                raise
            status = raw_response.status
            if status in expected:
                return raw_response
            if status in {408, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                continue
            if status in {401, 403}:
                raise ProviderAuthenticationError(
                    "El proveedor rechazó la autenticación", diagnostics=f"http_status={status}"
                )
            if status in {400, 402, 404, 409, 422}:
                raise ProviderRejected(
                    "El proveedor rechazó la operación", diagnostics=f"http_status={status}"
                )
            raise ProviderUnavailable(
                "El proveedor no está disponible", diagnostics=f"http_status={status}"
            )
        raise ProviderUnavailable("El proveedor no está disponible")

    def _send(self, method, url, *, headers, payload, params):
        request_response = getattr(self.transport, "request_response", None)
        if callable(request_response):
            raw_response = request_response(
                method,
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=self.timeout,
            )
        else:
            raw_response = self.transport.request(
                method,
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=self.timeout,
            )
        if isinstance(raw_response, ProviderHttpResponse):
            return ProviderHttpResponse(
                raw_response.status,
                {str(key).lower(): str(value) for key, value in raw_response.headers.items()},
                raw_response.body,
            )
        if not isinstance(raw_response, tuple) or len(raw_response) not in {2, 3}:
            raise ProviderInvalidResponse("El proveedor devolvió una respuesta inválida")
        if len(raw_response) == 2:
            status, body = raw_response
            response_headers = {}
        else:
            status, response_headers, body = raw_response
        return ProviderHttpResponse(
            int(status),
            {str(key).lower(): str(value) for key, value in response_headers.items()},
            body,
        )
