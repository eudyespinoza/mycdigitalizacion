import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_endpoint_reports_service_availability(client):
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
