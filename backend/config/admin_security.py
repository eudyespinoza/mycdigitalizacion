import hashlib
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.module_loading import import_string


class AdminLoginThrottle:
    def __init__(self, backend, *, maximum, timeout):
        self.backend = backend
        self.maximum = maximum
        self.timeout = timeout

    def reserve(self, key):
        if self.backend.add(key, 1, timeout=self.timeout):
            return 1
        try:
            return self.backend.incr(key)
        except ValueError:
            return 1 if self.backend.add(key, 1, timeout=self.timeout) else self.backend.incr(key)

    def is_blocked(self, key):
        return int(self.backend.get(key, 0)) >= self.maximum

    def clear(self, key):
        self.backend.delete(key)


def validate_admin_two_factor_settings(*, required, provider_path):
    if required and not str(provider_path or "").strip():
        raise ImproperlyConfigured(
            "ADMIN_2FA_PROVIDER is required when ADMIN_2FA_REQUIRED=true"
        )


def _two_factor_provider():
    validate_admin_two_factor_settings(
        required=settings.ADMIN_2FA_REQUIRED,
        provider_path=settings.ADMIN_2FA_PROVIDER,
    )
    provider_class = import_string(settings.ADMIN_2FA_PROVIDER)
    return provider_class()


def admin_two_factor_challenge(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseRedirect(f"{reverse('admin:login')}?next=/admin/")
    requested_next = request.GET.get("next", "/admin/")
    if not url_has_allowed_host_and_scheme(
        requested_next, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        requested_next = "/admin/"
    request.session["admin_2fa_pending_user_id"] = str(request.user.pk)
    request.session["admin_2fa_next"] = requested_next
    return _two_factor_provider().begin(request, reverse("admin-2fa-callback"))


def admin_two_factor_callback(request):
    pending_user_id = request.session.get("admin_2fa_pending_user_id")
    if not request.user.is_authenticated or pending_user_id != str(request.user.pk):
        return HttpResponseBadRequest("Verificación administrativa inválida")
    if not _two_factor_provider().verify(request):
        return HttpResponseBadRequest("No se pudo verificar el segundo factor")
    next_url = request.session.pop("admin_2fa_next", "/admin/")
    request.session.pop("admin_2fa_pending_user_id", None)
    request.session.cycle_key()
    request.session["admin_2fa_verified"] = True
    request.session["admin_2fa_user_id"] = str(request.user.pk)
    return HttpResponseRedirect(next_url)


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
        throttle = AdminLoginThrottle(
            caches["admin_login"],
            maximum=settings.ADMIN_LOGIN_MAX_ATTEMPTS,
            timeout=settings.ADMIN_LOGIN_LOCK_SECONDS,
        )
        if throttle.is_blocked(key):
            raise ValidationError(self.error_messages["rate_limited"], code="rate_limited")
        try:
            cleaned = super().clean()
        except ValidationError as exc:
            attempts = throttle.reserve(key)
            if attempts >= settings.ADMIN_LOGIN_MAX_ATTEMPTS:
                raise ValidationError(
                    self.error_messages["rate_limited"], code="rate_limited"
                ) from exc
            raise
        throttle.clear(key)
        return cleaned


class AdminTwoFactorGateMiddleware:
    """Session gate ready for a future OTP provider, disabled unless explicitly configured."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded = (
            "/admin/login/",
            "/admin/logout/",
            "/admin/2fa/",
            "/admin/2fa/callback/",
            settings.STATIC_URL,
        )
        if (
            settings.ADMIN_2FA_REQUIRED
            and request.path.startswith("/admin/")
            and not request.path.startswith(excluded)
            and getattr(request.user, "is_authenticated", False)
            and getattr(request.user, "is_staff", False)
            and (
                not request.session.get("admin_2fa_verified", False)
                or request.session.get("admin_2fa_user_id") != str(request.user.pk)
            )
        ):
            query = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"{reverse('admin-2fa-challenge')}?{query}")
        return self.get_response(request)


def configure_admin_site():
    admin.site.site_header = "mycdigitalizacion"
    admin.site.site_title = "mycdigitalizacion admin"
    admin.site.index_title = "Operaciones"
    admin.site.login_form = RateLimitedAdminAuthenticationForm
