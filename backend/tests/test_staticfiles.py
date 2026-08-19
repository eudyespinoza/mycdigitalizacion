from django.conf import settings


def test_production_static_contract_uses_whitenoise_manifest_storage():
    security_middleware = "django.middleware.security.SecurityMiddleware"
    whitenoise_middleware = "whitenoise.middleware.WhiteNoiseMiddleware"

    assert settings.MIDDLEWARE.index(whitenoise_middleware) == (
        settings.MIDDLEWARE.index(security_middleware) + 1
    )
    assert settings.STORAGES["staticfiles"]["BACKEND"] == (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
