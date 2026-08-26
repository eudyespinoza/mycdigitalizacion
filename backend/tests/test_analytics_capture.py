import uuid
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from analytics.models import AnalyticsEvent, AnalyticsSession

URL = "/api/v1/analytics/events/"


def payload(*, event_id=None, event_type="page_view", path="/catalogo", **extra):
    event = {
        "event_id": str(event_id or uuid.uuid4()),
        "event_type": event_type,
        "path": path,
        **extra,
    }
    return {"events": [event]}


@pytest.mark.django_db
def test_event_id_is_idempotent(client):
    event_id = uuid.uuid4()
    body = payload(event_id=event_id)

    assert client.post(URL, body, content_type="application/json").status_code == 202
    assert client.post(URL, body, content_type="application/json").status_code == 202

    assert AnalyticsEvent.objects.filter(event_id=event_id).count() == 1


@pytest.mark.django_db
def test_session_rotates_after_thirty_minutes(client, monkeypatch):
    first_at = timezone.now()
    monkeypatch.setattr("analytics.services.timezone.now", lambda: first_at)
    first = client.post(URL, payload(), content_type="application/json")
    first_cookie = first.cookies[settings.ANALYTICS_SESSION_COOKIE_NAME].value

    monkeypatch.setattr(
        "analytics.services.timezone.now",
        lambda: first_at + timedelta(minutes=31),
    )
    second = client.post(URL, payload(), content_type="application/json")

    assert second.status_code == 202
    assert second.cookies[settings.ANALYTICS_SESSION_COOKIE_NAME].value != first_cookie
    assert AnalyticsSession.objects.count() == 2


@pytest.mark.django_db
def test_capture_rejects_unknown_events_dimensions_and_oversized_batches(client):
    unknown_event = client.post(
        URL,
        payload(event_type="purchase"),
        content_type="application/json",
    )
    unknown_dimension = client.post(
        URL,
        payload(dimensions={"email": "buyer@example.test"}),
        content_type="application/json",
    )
    oversized = client.post(
        URL,
        {"events": [payload()["events"][0] for _ in range(21)]},
        content_type="application/json",
    )

    assert unknown_event.status_code == 400
    assert unknown_dimension.status_code == 400
    assert oversized.status_code == 400
    assert not AnalyticsEvent.objects.exists()


@pytest.mark.django_db
def test_sensitive_and_operational_paths_are_excluded(client):
    for path in (
        "/gestion/usuarios",
        "/api/v1/customers/me/",
        "/healthz",
        "/checkout/payment-status/private-token",
    ):
        response = client.post(URL, payload(path=path), content_type="application/json")
        assert response.status_code == 202
        assert response.json() == {"accepted": 0}

    assert not AnalyticsSession.objects.exists()
    assert not AnalyticsEvent.objects.exists()


@pytest.mark.django_db
def test_capture_persists_only_normalized_attribution(client):
    response = client.post(
        URL,
        payload(
            path="/catalogo?token=secret",
            dimensions={
                "utm_source": " Instagram ",
                "utm_medium": " Social ",
                "utm_campaign": " Lanzamiento 2026 ",
                "referrer": "https://search.example/path?q=sensitive",
            },
        ),
        content_type="application/json",
        HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 13; Mobile) full-agent-detail",
    )

    assert response.status_code == 202
    session = AnalyticsSession.objects.get()
    event = AnalyticsEvent.objects.get()
    assert session.source == "instagram"
    assert session.medium == "social"
    assert session.campaign == "lanzamiento 2026"
    assert session.referrer_domain == "search.example"
    assert session.device == "mobile"
    assert session.entry_path == "/catalogo"
    assert event.path == "/catalogo"
    assert "secret" not in str(session.__dict__)
    assert "full-agent-detail" not in str(session.__dict__)


@pytest.mark.django_db
def test_product_view_requires_a_real_matching_product_and_variant(client):
    response = client.post(
        URL,
        payload(event_type="product_view", product_id=99999, variant_id=99999),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not AnalyticsEvent.objects.exists()


@pytest.mark.django_db
def test_successful_capture_sets_private_lax_cookies(client):
    response = client.post(URL, payload(), content_type="application/json")

    visitor = response.cookies[settings.ANALYTICS_VISITOR_COOKIE_NAME]
    session = response.cookies[settings.ANALYTICS_SESSION_COOKIE_NAME]
    assert visitor["httponly"] is True
    assert session["httponly"] is True
    assert visitor["samesite"] == "Lax"
    assert session["samesite"] == "Lax"
