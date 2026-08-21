from django.conf import settings
from django.db import DatabaseError, connection
from django.http import Http404, JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.static import serve as serve_static
from redis import Redis
from redis.exceptions import RedisError


def healthz(_: object) -> JsonResponse:
    """Expose process availability without disclosing operational details."""
    return JsonResponse({"status": "ok"})


def development_media(request, path: str):
    """Serve uploaded files only for the local Django development server."""
    if not settings.DEBUG:
        raise Http404
    return serve_static(request, path, document_root=settings.MEDIA_ROOT)


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
