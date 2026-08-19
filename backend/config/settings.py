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

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
if "pytest" in sys.modules:
    DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {"DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]}
CELERY_BROKER_URL = environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
