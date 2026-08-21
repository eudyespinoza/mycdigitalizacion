from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, PermissionDenied


class CsrfFailed(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "csrf_failed"

    def __init__(self):
        super().__init__(
            detail={
                "code": "csrf_failed",
                "detail": (
                    "La sesión de seguridad venció. "
                    "Actualizá la página e intentá nuevamente."
                ),
            }
        )


class JsonSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied as exc:
            raise CsrfFailed() from exc


class JsonSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "config.authentication.JsonSessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
