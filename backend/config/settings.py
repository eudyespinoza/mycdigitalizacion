import sys
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from os import environ
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "change-me-for-local-development",
        "unsafe-development-key-change-me",
        "localhost",
        "example.com",
        "ops@example.com",
        "development-only-personal-data-key",
        "container-build-personal-data-encryption-key-not-for-runtime",
        "container-build-signing-key-that-is-not-a-placeholder",
        "ephemeral-build-only-personal-data-key-never-used-at-runtime",
        "container-build-database-password-not-a-placeholder",
        "build.example.test",
    }
)


def strict_boolean(environment: Mapping[str, str], field: str, *, default: str = "false") -> bool:
    raw_value = environment.get(field, default).strip().lower()
    if raw_value not in {"true", "false"}:
        raise ImproperlyConfigured(f"{field} must be true or false")
    return raw_value == "true"


def admin_cache_config(environment: Mapping[str, str]) -> dict[str, str]:
    if environment.get("APP_ENV", "").strip().lower() == "production":
        return {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": environment.get("REDIS_URL", "redis://redis:6379/0"),
            "KEY_PREFIX": "mycd-admin",
        }
    return {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mycd-admin-development-fallback",
    }


def validate_runtime_environment(environment: Mapping[str, str]) -> None:
    """Reject accidental production startup with development configuration."""
    app_env = environment.get("APP_ENV", "").strip().lower()
    if app_env not in {"development", "production", "test"}:
        raise ImproperlyConfigured("APP_ENV must be development, production, or test")

    mercado_pago_live_mode = strict_boolean(environment, "MERCADOPAGO_LIVE_MODE")
    carrier_enabled = strict_boolean(environment, "CORREO_ARGENTINO_ENABLED")

    mp_fields = {
        field: environment.get(field, "").strip()
        for field in (
            "MERCADOPAGO_ACCESS_TOKEN",
            "MERCADOPAGO_WEBHOOK_SECRET",
            "MERCADOPAGO_COLLECTOR_ID",
        )
    }
    mercado_pago_enabled = mercado_pago_live_mode or any(mp_fields.values())
    if mercado_pago_enabled and not all(mp_fields.values()):
        missing = next(field for field, value in mp_fields.items() if not value)
        raise ImproperlyConfigured(f"{missing} is required when Mercado Pago is configured")

    if carrier_enabled:
        carrier_environment = environment.get("CORREO_ARGENTINO_ENVIRONMENT", "").lower()
        if carrier_environment not in {"qa", "production"}:
            raise ImproperlyConfigured("CORREO_ARGENTINO_ENVIRONMENT must be qa or production")
        required = (
            "CORREO_ARGENTINO_USERNAME",
            "CORREO_ARGENTINO_PASSWORD",
            "CORREO_ARGENTINO_CUSTOMER_ID",
            "CORREO_ARGENTINO_ORIGIN_POSTAL_CODE",
            "CORREO_ARGENTINO_QA_BASE_URL"
            if carrier_environment == "qa"
            else "CORREO_ARGENTINO_PRODUCTION_BASE_URL",
        )
        if any(not environment.get(field, "").strip() for field in required):
            raise ImproperlyConfigured(
                "CORREO_ARGENTINO credentials, customer, origin, and base URL are required"
            )
        base_url = environment[required[-1]].strip()
        if urlsplit(base_url).scheme != "https":
            raise ImproperlyConfigured("CORREO_ARGENTINO base URL must use HTTPS")

    if app_env != "production":
        return

    for field, minimum_length in (
        ("DJANGO_SECRET_KEY", 32),
        ("POSTGRES_PASSWORD", 16),
        ("SITE_ADDRESS", 1),
        ("DJANGO_ALLOWED_HOSTS", 1),
        ("PERSONAL_DATA_ENCRYPTION_KEY", 32),
    ):
        value = environment.get(field, "").strip()
        if value.lower() in PLACEHOLDER_VALUES or len(value) < minimum_length:
            raise ImproperlyConfigured(f"{field} must be a non-placeholder production value")

    sid_mode = environment.get("SID_MODE", "disabled").strip().lower()
    if sid_mode not in {"disabled", "sandbox", "production"}:
        raise ImproperlyConfigured("SID_MODE must be disabled, sandbox, or production")
    if sid_mode != "disabled" and not all(
        environment.get(field, "").strip() for field in ("SID_BASE_URL", "SID_ACCESS_TOKEN")
    ):
        raise ImproperlyConfigured("SID_BASE_URL and SID_ACCESS_TOKEN are required")
    if sid_mode != "disabled" and urlsplit(environment["SID_BASE_URL"]).scheme != "https":
        raise ImproperlyConfigured("SID_BASE_URL must use HTTPS")

    try:
        webhook_tolerance = int(environment.get("MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS", "300"))
    except ValueError as exc:
        raise ImproperlyConfigured(
            "MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS must be an integer"
        ) from exc
    if webhook_tolerance <= 0:
        raise ImproperlyConfigured("MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS must be positive")

    surcharge_type = environment.get("SHIPPING_SURCHARGE_TYPE", "exact").lower()
    if surcharge_type not in {"exact", "percentage"}:
        raise ImproperlyConfigured("SHIPPING_SURCHARGE_TYPE must be exact or percentage")
    for field in ("SHIPPING_SURCHARGE_VALUE", "SHIPPING_FREE_THRESHOLD"):
        raw = environment.get(field, "").strip()
        if not raw:
            continue
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise ImproperlyConfigured(f"{field} must be numeric") from exc
        if value < 0:
            raise ImproperlyConfigured(f"{field} must not be negative")


APP_ENV = environ.get("APP_ENV", "").lower()
validate_runtime_environment(environ)

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = environ.get("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "" if APP_ENV == "production" else "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
CURRENT_CONSENT_VERSION = "privacy-v1"

SESSION_COOKIE_SECURE = APP_ENV == "production"
CSRF_COOKIE_SECURE = APP_ENV == "production"
CSRF_FAILURE_VIEW = "config.views.csrf_failure"
SECURE_SSL_REDIRECT = APP_ENV == "production"
SECURE_HSTS_SECONDS = 31_536_000 if APP_ENV == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = APP_ENV == "production"
SECURE_HSTS_PRELOAD = APP_ENV == "production"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "backoffice",
    "accounts",
    "catalog",
    "commerce",
    "locations",
    "landing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.observability.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.admin_security.AdminTwoFactorGateMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": environ.get("POSTGRES_DB", "mycdigitalizacion"),
        "USER": environ.get("POSTGRES_USER", "mycdigitalizacion"),
        "PASSWORD": environ.get("POSTGRES_PASSWORD", "change-me-for-local-development"),
        "HOST": environ.get("POSTGRES_HOST", "localhost"),
        "PORT": environ.get("POSTGRES_PORT", "5432"),
    }
}
if "pytest" in sys.modules and environ.get("USE_POSTGRES_TEST_DB", "false").lower() != "true":
    DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(environ.get("MEDIA_ROOT", BASE_DIR / "media"))
MAX_IMAGE_UPLOAD_BYTES = int(environ.get("MAX_IMAGE_UPLOAD_BYTES", str(12 * 1024 * 1024)))
MAX_IMAGE_WIDTH = int(environ.get("MAX_IMAGE_WIDTH", "6000"))
MAX_IMAGE_HEIGHT = int(environ.get("MAX_IMAGE_HEIGHT", "6000"))
MAX_IMAGE_PIXELS = int(environ.get("MAX_IMAGE_PIXELS", "24000000"))
MEDIA_DERIVATIVE_FORMATS = ("AVIF", "WEBP")
MEDIA_RESPONSIVE_WIDTHS = (320, 640, 960, 1440)
CATALOG_CSV_MAX_BYTES = int(environ.get("CATALOG_CSV_MAX_BYTES", str(2 * 1024 * 1024)))
CATALOG_CSV_MAX_ROWS = int(environ.get("CATALOG_CSV_MAX_ROWS", "5000"))
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

ADMIN_LOGIN_MAX_ATTEMPTS = int(environ.get("ADMIN_LOGIN_MAX_ATTEMPTS", "5"))
ADMIN_LOGIN_LOCK_SECONDS = int(environ.get("ADMIN_LOGIN_LOCK_SECONDS", "900"))
ADMIN_2FA_REQUIRED = environ.get("ADMIN_2FA_REQUIRED", "false").lower() == "true"
ADMIN_2FA_PROVIDER = environ.get("ADMIN_2FA_PROVIDER", "")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mycd-default",
    },
    "admin_login": admin_cache_config(environ),
}

if ADMIN_2FA_REQUIRED and not ADMIN_2FA_PROVIDER.strip():
    raise ImproperlyConfigured(
        "ADMIN_2FA_PROVIDER is required when ADMIN_2FA_REQUIRED=true"
    )

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "verify_email": "10/hour",
        "verify_ip": "20/hour",
    },
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SPECTACULAR_SETTINGS = {
    "TITLE": "mycdigitalizacion API",
    "VERSION": "1.0.0",
}
PERSONAL_DATA_ENCRYPTION_KEY = environ.get(
    "PERSONAL_DATA_ENCRYPTION_KEY", "development-only-personal-data-key"
)
CELERY_BROKER_URL = environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "config.observability.JsonFormatter",
            "service": environ.get("SERVICE_NAME", "backend"),
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

PUBLIC_BACKEND_URL = environ.get(
    "PUBLIC_BACKEND_URL", f"https://{environ.get('SITE_ADDRESS', 'localhost')}"
).rstrip("/")
SID_MODE = environ.get("SID_MODE", "disabled").lower()
SID_BASE_URL = environ.get("SID_BASE_URL", "")
SID_ACCESS_TOKEN = environ.get("SID_ACCESS_TOKEN", "")
MERCADOPAGO_ACCESS_TOKEN = environ.get("MERCADOPAGO_ACCESS_TOKEN", "")
MERCADOPAGO_WEBHOOK_SECRET = environ.get("MERCADOPAGO_WEBHOOK_SECRET", "")
MERCADOPAGO_COLLECTOR_ID = environ.get("MERCADOPAGO_COLLECTOR_ID", "")
MERCADOPAGO_LIVE_MODE = strict_boolean(environ, "MERCADOPAGO_LIVE_MODE")
MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS = int(
    environ.get("MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS", "300")
)
CORREO_ARGENTINO_ENABLED = strict_boolean(environ, "CORREO_ARGENTINO_ENABLED")
CORREO_ARGENTINO_ENVIRONMENT = environ.get("CORREO_ARGENTINO_ENVIRONMENT", "qa").lower()
CORREO_ARGENTINO_QA_BASE_URL = environ.get(
    "CORREO_ARGENTINO_QA_BASE_URL", "https://apitest.correoargentino.com.ar/micorreo/v1"
)
CORREO_ARGENTINO_PRODUCTION_BASE_URL = environ.get(
    "CORREO_ARGENTINO_PRODUCTION_BASE_URL", "https://api.correoargentino.com.ar/micorreo/v1"
)
CORREO_ARGENTINO_USERNAME = environ.get("CORREO_ARGENTINO_USERNAME", "")
CORREO_ARGENTINO_PASSWORD = environ.get("CORREO_ARGENTINO_PASSWORD", "")
CORREO_ARGENTINO_CUSTOMER_ID = environ.get("CORREO_ARGENTINO_CUSTOMER_ID", "")
CORREO_ARGENTINO_ORIGIN_POSTAL_CODE = environ.get("CORREO_ARGENTINO_ORIGIN_POSTAL_CODE", "")
SHIPPING_SURCHARGE_TYPE = environ.get("SHIPPING_SURCHARGE_TYPE", "exact")
SHIPPING_SURCHARGE_VALUE = environ.get("SHIPPING_SURCHARGE_VALUE", "0")
SHIPPING_FREE_THRESHOLD = environ.get("SHIPPING_FREE_THRESHOLD", "")

CELERY_BEAT_SCHEDULE = {
    "sync-andreani-localities": {
        "task": "locations.tasks.sync_andreani_localities",
        "schedule": 86_400,
    },
    "release-expired-reservations": {
        "task": "commerce.tasks.release_expired_reservations",
        "schedule": 60,
    },
    "reconcile-pending-payments": {
        "task": "commerce.tasks.reconcile_pending_payments",
        "schedule": 300,
    },
    "sweep-stale-webhook-events": {
        "task": "commerce.tasks.sweep_stale_webhook_events",
        "schedule": 60,
    },
    "resume-pending-shipments": {
        "task": "commerce.tasks.resume_pending_shipments",
        "schedule": 300,
    },
    "reconcile-tracking": {
        "task": "commerce.tasks.reconcile_tracking",
        "schedule": 900,
    },
    "retry-safe-notifications": {
        "task": "commerce.tasks.retry_safe_notifications",
        "schedule": 300,
    },
    "expire-verification-challenges": {
        "task": "commerce.tasks.expire_verification_challenges",
        "schedule": 300,
    },
}
