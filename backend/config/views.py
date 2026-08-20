from django.conf import settings
from django.contrib import admin
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.csrf import csrf_failure as django_csrf_failure
from redis import Redis
from redis.exceptions import RedisError


def healthz(_: object) -> JsonResponse:
    """Expose process availability without disclosing operational details."""
    return JsonResponse({"status": "ok"})


def database_is_ready():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except DatabaseError:
        return False


def redis_is_ready():
    try:
        client = Redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return bool(client.ping())
    except (RedisError, OSError, ValueError):
        return False


def readyz(_: object) -> JsonResponse:
    database_ready = database_is_ready()
    redis_ready = redis_is_ready()
    ready = database_ready and redis_ready
    return JsonResponse(
        {
            "status": "ready" if ready else "not_ready",
            "dependencies": {
                "database": "ok" if database_ready else "unavailable",
                "redis": "ok" if redis_ready else "unavailable",
            },
        },
        status=200 if ready else 503,
    )


def admin_integrations(request):
    """Show provider readiness to staff without exposing provider credentials."""
    mercado_pago_fields = {
        "access_token": bool(settings.MERCADOPAGO_ACCESS_TOKEN),
        "webhook_secret": bool(settings.MERCADOPAGO_WEBHOOK_SECRET),
        "collector_id": bool(settings.MERCADOPAGO_COLLECTOR_ID),
    }
    context = {
        **admin.site.each_context(request),
        "title": "Integraciones",
        "mercado_pago": {
            "configured": all(mercado_pago_fields.values()),
            "fields": mercado_pago_fields,
            "collector_id": settings.MERCADOPAGO_COLLECTOR_ID,
            "mode": "Producción" if settings.MERCADOPAGO_LIVE_MODE else "Modo de pruebas",
            "webhook_url": request.build_absolute_uri(reverse("mercadopago-webhook")),
        },
    }
    return render(request, "admin/integrations.html", context)


def csrf_failure(request, reason="", template_name="403_csrf.html"):
    """Return a stable, non-diagnostic error contract for API CSRF failures."""
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "code": "csrf_failed",
                "detail": (
                    "La sesión de seguridad venció. "
                    "Actualizá la página e intentá nuevamente."
                ),
            },
            status=403,
        )
    return django_csrf_failure(request, reason=reason, template_name=template_name)
