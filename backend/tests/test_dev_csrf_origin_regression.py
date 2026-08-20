from django.conf import settings


def test_local_storefront_origin_is_trusted_outside_production():
    if settings.APP_ENV != "production":
        assert "http://localhost:3000" in settings.CSRF_TRUSTED_ORIGINS
        assert "http://127.0.0.1:3000" in settings.CSRF_TRUSTED_ORIGINS
