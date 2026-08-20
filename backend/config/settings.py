import sys
from collections.abc import Mapping
from os import environ
from pathlib import Path

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


def validate_runtime_environment(environment: Mapping[str, str]) -> None:
    """Reject accidental production startup with development configuration."""
    app_env = environment.get("APP_ENV", "").strip().lower()
    if app_env not in {"development", "production", "test"}:
        raise ImproperlyConfigured("APP_ENV must be development, production, or test")

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


APP_ENV = environ.get("APP_ENV", "").lower()
validate_runtime_environment(environ)

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = environ.get("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CURRENT_CONSENT_VERSION = "privacy-v1"

SESSION_COOKIE_SECURE = APP_ENV == "production"
CSRF_COOKIE_SECURE = APP_ENV == "production"
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
    "accounts",
    "catalog",
    "commerce",
    "locations",
    "landing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
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
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

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
