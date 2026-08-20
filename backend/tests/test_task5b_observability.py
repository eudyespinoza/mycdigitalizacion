import io
import json
import logging
import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from config.observability import (
    JsonFormatter,
    RequestContextMiddleware,
    bind_task_context,
    clear_log_context,
    current_log_context,
    publish_task_context,
)


def formatted_record(message, **extra):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="backend"))
    logger = logging.getLogger("task5b.observability.test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info(message, extra=extra)
    return json.loads(stream.getvalue())


def test_request_middleware_accepts_only_uuid_and_returns_same_correlation_id():
    supplied = str(uuid.uuid4())
    request = RequestFactory().get(
        "/api/v1/products/?email=ana@example.com", HTTP_X_REQUEST_ID=supplied
    )
    response = RequestContextMiddleware(lambda incoming: HttpResponse(status=204))(request)

    assert response["X-Request-ID"] == supplied
    assert current_log_context() == {}

    hostile = RequestFactory().get("/healthz", HTTP_X_REQUEST_ID="attacker-controlled\nvalue")
    replaced = RequestContextMiddleware(lambda incoming: HttpResponse(status=200))(hostile)
    assert replaced["X-Request-ID"] != "attacker-controlled\nvalue"
    uuid.UUID(replaced["X-Request-ID"])


def test_json_formatter_whitelists_fields_and_redacts_pii_and_query_strings():
    record = formatted_record(
        "failed for ana@example.com DNI 12345678 at /checkout?token=secret",
        event="request.complete",
        request_id=str(uuid.uuid4()),
        method="POST",
        path="/checkout?token=secret&email=ana@example.com",
        status=400,
        authorization="Bearer should-never-serialize",
        cookie="session=should-never-serialize",
    )

    encoded = json.dumps(record)
    assert record["service"] == "backend"
    assert record["event"] == "request.complete"
    assert record["path"] == "/checkout"
    assert record["status"] == 400
    assert "secret" not in encoded
    assert "ana@example.com" not in encoded
    assert "12345678" not in encoded
    assert "should-never-serialize" not in encoded


def test_request_exception_log_keeps_correlation_without_query_cookie_or_pii(caplog):
    request_id = str(uuid.uuid4())
    request = RequestFactory().get(
        "/api/v1/orders/?email=ana@example.com&token=secret",
        HTTP_X_REQUEST_ID=request_id,
        HTTP_COOKIE="session=should-never-serialize",
    )

    def fail(incoming):
        raise RuntimeError("provider refused ana@example.com?token=secret")

    with caplog.at_level(logging.INFO, logger="app.request"), pytest.raises(RuntimeError):
        RequestContextMiddleware(fail)(request)

    record = next(item for item in caplog.records if item.name == "app.request")
    payload = json.loads(JsonFormatter(service="backend").format(record))
    encoded = json.dumps(payload)
    assert payload["request_id"] == request_id
    assert payload["path"] == "/api/v1/orders/"
    assert payload["status"] == 500
    assert "ana@example.com" not in encoded
    assert "token=secret" not in encoded
    assert "should-never-serialize" not in encoded


def test_celery_publish_propagates_request_id_and_worker_binds_job_id():
    request_id = str(uuid.uuid4())
    clear_log_context()
    from config.observability import set_log_context

    set_log_context(request_id=request_id)
    headers = {}
    publish_task_context(headers=headers)
    assert headers["request_id"] == request_id

    class Request:
        pass

    class Task:
        request = Request()

    Task.request.headers = headers
    bind_task_context(task_id="job-42", task=Task())
    assert current_log_context() == {"request_id": request_id, "job_id": "job-42"}
    clear_log_context()


def test_formatter_uses_bound_context_for_worker_and_beat_events():
    clear_log_context()
    from config.observability import set_log_context

    request_id = str(uuid.uuid4())
    set_log_context(request_id=request_id, job_id="scheduled-job")
    record = formatted_record("task completed", event="task.complete")
    assert record["request_id"] == request_id
    assert record["job_id"] == "scheduled-job"
    clear_log_context()
