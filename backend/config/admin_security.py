import hashlib
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect


class RateLimitedAdminAuthenticationForm(AdminAuthenticationForm):
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "rate_limited": "Demasiados intentos. Esperá antes de volver a ingresar.",
    }

    def _cache_key(self):
        username = str(self.data.get("username", "")).strip().lower()
        address = self.request.META.get("REMOTE_ADDR", "unknown") if self.request else "unknown"
        digest = hashlib.sha256(f"{address}:{username}".encode()).hexdigest()
        return f"admin-login-failures:{digest}"

    def clean(self):
        key = self._cache_key()
        attempts = int(cache.get(key, 0))
        maximum = settings.ADMIN_LOGIN_MAX_ATTEMPTS
        if attempts >= maximum:
            raise ValidationError(self.error_messages["rate_limited"], code="rate_limited")
        try:
            cleaned = super().clean()
        except ValidationError as exc:
            attempts += 1
            cache.set(key, attempts, timeout=settings.ADMIN_LOGIN_LOCK_SECONDS)
            if attempts >= maximum:
                raise ValidationError(
                    self.error_messages["rate_limited"], code="rate_limited"
                ) from exc
            raise
        cache.delete(key)
        return cleaned


class AdminTwoFactorGateMiddleware:
    """Session gate ready for a future OTP provider, disabled unless explicitly configured."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        verification_url = settings.ADMIN_2FA_VERIFICATION_URL
        excluded = (
            "/admin/login/",
            "/admin/logout/",
            verification_url,
            settings.STATIC_URL,
        )
        if (
            settings.ADMIN_2FA_REQUIRED
            and request.path.startswith("/admin/")
            and not request.path.startswith(excluded)
            and getattr(request.user, "is_authenticated", False)
            and getattr(request.user, "is_staff", False)
            and not request.session.get("admin_2fa_verified", False)
        ):
            query = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"{verification_url}?{query}")
        return self.get_response(request)


def configure_admin_site():
    admin.site.site_header = "mycdigitalizacion"
    admin.site.site_title = "mycdigitalizacion admin"
    admin.site.index_title = "Operaciones"
    admin.site.login_form = RateLimitedAdminAuthenticationForm
