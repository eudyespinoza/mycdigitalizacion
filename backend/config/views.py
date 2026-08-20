from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure


def healthz(_: object) -> JsonResponse:
    """Expose process availability without disclosing operational details."""
    return JsonResponse({"status": "ok"})


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
