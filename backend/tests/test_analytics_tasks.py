import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from analytics.models import (
    AnalyticsDailyChannel,
    AnalyticsDailyProduct,
    AnalyticsEvent,
    AnalyticsSession,
)


def make_product():
    from catalog.models import Category, Product

    category, _ = Category.objects.get_or_create(name="Rollups", slug="rollups")
    return Product.objects.create(
        category=category,
        name=f"Producto {uuid.uuid4().hex[:8]}",
        slug=f"rollup-{uuid.uuid4().hex}",
    )


@pytest.mark.django_db
def test_rollup_is_idempotent_and_aggregates_sessions_and_products():
    from analytics.tasks import rollup_analytics_day

    now = timezone.now()
    product = make_product()
    session = AnalyticsSession.objects.create(
        visitor_hash="c" * 64,
        started_at=now,
        last_seen_at=now,
        source="instagram",
        medium="social",
        campaign="agosto",
        device="mobile",
        entry_path="/catalogo",
        viewed_product=True,
        added_to_cart=True,
    )
    AnalyticsEvent.objects.create(
        event_id=uuid.uuid4(),
        session=session,
        event_type=AnalyticsEvent.EventType.PRODUCT_VIEW,
        product=product,
        path=f"/producto/{product.slug}",
        occurred_at=now,
    )
    AnalyticsEvent.objects.create(
        event_id=uuid.uuid4(),
        session=session,
        event_type=AnalyticsEvent.EventType.ADD_TO_CART,
        product=product,
        quantity=2,
        path="/carrito",
        occurred_at=now,
    )

    first = rollup_analytics_day(timezone.localdate(now))
    second = rollup_analytics_day(timezone.localdate(now))

    assert first == second
    product_row = AnalyticsDailyProduct.objects.get(product=product)
    channel_row = AnalyticsDailyChannel.objects.get(source="instagram")
    assert product_row.views == 1
    assert product_row.viewing_sessions == 1
    assert product_row.cart_additions == 1
    assert channel_row.sessions == 1
    assert channel_row.visitors == 1
    assert channel_row.product_views == 1
    assert AnalyticsDailyProduct.objects.count() == 1
    assert AnalyticsDailyChannel.objects.count() == 1


@pytest.mark.django_db
def test_retention_keeps_sessions_longer_than_events():
    from analytics.tasks import purge_expired_analytics

    now = timezone.now()
    product = make_product()
    retained_session = AnalyticsSession.objects.create(
        visitor_hash="d" * 64,
        started_at=now - timedelta(days=700),
        last_seen_at=now - timedelta(days=91),
        entry_path="/",
    )
    expired_session = AnalyticsSession.objects.create(
        visitor_hash="e" * 64,
        started_at=now - timedelta(days=731),
        last_seen_at=now - timedelta(days=731),
        entry_path="/",
    )
    AnalyticsEvent.objects.create(
        event_id=uuid.uuid4(),
        session=retained_session,
        event_type=AnalyticsEvent.EventType.PRODUCT_VIEW,
        product=product,
        occurred_at=now - timedelta(days=91),
    )
    AnalyticsDailyProduct.objects.create(
        day=timezone.localdate(now - timedelta(days=731)),
        product=product,
        product_revenue=Decimal("0"),
    )

    result = purge_expired_analytics(now=now)

    assert result["events"] == 1
    assert AnalyticsSession.objects.filter(pk=retained_session.pk).exists()
    assert not AnalyticsSession.objects.filter(pk=expired_session.pk).exists()
    assert not AnalyticsEvent.objects.exists()
    assert not AnalyticsDailyProduct.objects.exists()


@pytest.mark.django_db
def test_cache_invalidation_uses_versions_without_key_scans():
    from analytics.selectors import (
        analytics_cache_version,
        invalidate_commercial_analytics,
        invalidate_web_analytics,
    )

    web_before = analytics_cache_version("web")
    commercial_before = analytics_cache_version("commercial")

    invalidate_web_analytics()
    invalidate_commercial_analytics()

    assert analytics_cache_version("web") == web_before + 1
    assert analytics_cache_version("commercial") == commercial_before + 1


@pytest.mark.django_db
def test_recent_rollup_task_returns_a_json_serializable_result():
    from analytics.tasks import rollup_recent_analytics

    result = rollup_recent_analytics(now=timezone.now())

    assert json.loads(json.dumps(result))[0]["products"] == 0


def test_refund_change_invalidates_commercial_analytics():
    from analytics.selectors import analytics_cache_version
    from analytics.services import record_refund_change

    before = analytics_cache_version("commercial")

    record_refund_change(refund=object())

    assert analytics_cache_version("commercial") == before + 1
