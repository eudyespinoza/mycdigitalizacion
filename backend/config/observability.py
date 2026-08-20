from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from time import monotonic
from urllib.parse import urlsplit

from celery.signals import before_task_publish, task_failure, task_postrun, task_prerun

_log_context: ContextVar[dict[str, str] | None] = ContextVar("log_context", default=None)
_email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_personal_number = re.compile(r"(?<!\d)\d{7,15}(?!\d)")
_query = re.compile(r"(?P<path>(?:https?://[^\s?]+|/[^\s?]*))\?[^\s]+")


def current_log_context() -> dict[str, str]:
    return dict(_log_context.get() or {})


def set_log_context(**values: str) -> None:
    _log_context.set({key: value for key, value in values.items() if value})


def clear_log_context(*args, **kwargs) -> None:
    _log_context.set({})


def _request_id(value: object) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        parsed = uuid.uuid4()
    return str(parsed)


def _safe_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = _query.sub(r"\g<path>", text)
    if text.startswith(("/", "http://", "https://")):
        parsed = urlsplit(text)
        text = parsed.path or "/"
    text = _email.sub("[redacted-email]", text)
    return _personal_number.sub("[redacted-number]", text)


class JsonFormatter(logging.Formatter):
    """Small allow-listed JSON schema shared by web, worker, and beat logs."""

    _fields = ("event", "request_id", "job_id", "method", "path", "status", "duration_ms")

    def __init__(self, service: str = "backend") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        context = current_log_context()
        output: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "logger": record.name,
            "message": _safe_text(record.getMessage()),
        }
        for field in self._fields:
            value = getattr(record, field, context.get(field))
            if value in (None, ""):
                continue
            output[field] = _safe_text(value) if field in {"method", "path"} else value
        return json.dumps(output, ensure_ascii=False, separators=(",", ":"))


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("app.request")

    def __call__(self, request):
        request_id = _request_id(request.META.get("HTTP_X_REQUEST_ID"))
        set_log_context(request_id=request_id)
        started = monotonic()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-ID"] = request_id
            return response
        finally:
            self.logger.info(
                "request completed",
                extra={
                    "event": "request.complete",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "status": status,
                    "duration_ms": round((monotonic() - started) * 1000, 2),
                },
            )
            clear_log_context()


@before_task_publish.connect
def publish_task_context(headers=None, **kwargs) -> None:
    if headers is None:
        return
    context = current_log_context()
    headers["request_id"] = _request_id(context.get("request_id"))


@task_prerun.connect
def bind_task_context(task_id=None, task=None, **kwargs) -> None:
    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    set_log_context(request_id=_request_id(headers.get("request_id")), job_id=str(task_id or ""))


task_postrun.connect(clear_log_context)
task_failure.connect(clear_log_context)
