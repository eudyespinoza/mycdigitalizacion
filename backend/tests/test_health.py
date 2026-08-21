import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_endpoint_reports_service_availability(client):
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_development_server_delivers_uploaded_media(client, settings, tmp_path):
    media = tmp_path / "catalog" / "preview.jpg"
    media.parent.mkdir()
    media.write_bytes(b"uploaded-product-image")
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path

    response = client.get("/media/catalog/preview.jpg")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"uploaded-product-image"


def test_backend_does_not_deliver_media_when_debug_is_disabled(client, settings, tmp_path):
    media = tmp_path / "catalog" / "private.jpg"
    media.parent.mkdir()
    media.write_bytes(b"production-media")
    settings.DEBUG = False
    settings.MEDIA_ROOT = tmp_path

    response = client.get("/media/catalog/private.jpg")

    assert response.status_code == 404
