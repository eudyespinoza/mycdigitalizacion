from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from analytics.models import (
    AnalyticsConversion,
    AnalyticsDailyChannel,
    AnalyticsDailyProduct,
    AnalyticsEvent,
    AnalyticsSession,
)
from analytics.selectors import (
    invalidate_commercial_analytics,
    invalidate_web_analytics,
)


@dataclass(frozen=True)
class RollupResult:
    day: object
    products: int
    channels: int


def _day_bounds(day):
    zone = ZoneInfo(settings.TIME_ZONE)
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start, start + timedelta(days=1)


def _product_rows(start, end):
    rows = defaultdict(
        lambda: {
            "views": 0,
            "viewing_sessions": 0,
            "cart_additions": 0,
            "attributed_checkouts": 0,
            "paid_orders": 0,
            "units": 0,
            "product_revenue": Decimal("0"),
            "discounts": Decimal("0"),
        }
    )
    views = (
        AnalyticsEvent.objects.filter(
            occurred_at__gte=start,
            occurred_at__lt=end,
            event_type=AnalyticsEvent.EventType.PRODUCT_VIEW,
            product_id__isnull=False,
        )
        .values("product_id")
        .annotate(total=Count("id"), sessions=Count("session_id", distinct=True))
    )
    for item in views:
        rows[item["product_id"]]["views"] = item["total"]
        rows[item["product_id"]]["viewing_sessions"] = item["sessions"]

    additions = (
        AnalyticsEvent.objects.filter(
            occurred_at__gte=start,
            occurred_at__lt=end,
            event_type=AnalyticsEvent.EventType.ADD_TO_CART,
            product_id__isnull=False,
        )
        .values("product_id")
        .annotate(total=Count("id"))
    )
    for item in additions:
        rows[item["product_id"]]["cart_additions"] = item["total"]

    checkout_orders = {}
    from analytics.models import AnalyticsOrderAttribution

    for attribution in AnalyticsOrderAttribution.objects.filter(
        attributed_at__gte=start,
        attributed_at__lt=end,
    ).prefetch_related("order__items__variant__product"):
        for item in attribution.order.items.all():
            if item.variant_id:
                product_id = item.variant.product_id
                checkout_orders.setdefault(product_id, set()).add(attribution.order_id)
    for product_id, order_ids in checkout_orders.items():
        rows[product_id]["attributed_checkouts"] = len(order_ids)

    paid_orders = {}
    for conversion in AnalyticsConversion.objects.filter(
        approved_at__gte=start,
        approved_at__lt=end,
    ).prefetch_related("order__items__variant__product"):
        for item in conversion.order.items.all():
            if not item.variant_id:
                continue
            product_id = item.variant.product_id
            paid_orders.setdefault(product_id, set()).add(conversion.order_id)
            rows[product_id]["units"] += item.quantity
            rows[product_id]["product_revenue"] += item.line_total_snapshot
            rows[product_id]["discounts"] += item.discount_snapshot
    for product_id, order_ids in paid_orders.items():
        rows[product_id]["paid_orders"] = len(order_ids)
    return rows


def _channel_rows(start, end):
    rows = defaultdict(
        lambda: {
            "sessions": 0,
            "visitor_hashes": set(),
            "product_views": 0,
            "cart_additions": 0,
            "checkout_starts": 0,
            "delivery_selections": 0,
            "payment_starts": 0,
            "paid_orders": 0,
            "attributed_revenue": Decimal("0"),
        }
    )
    fields = ("source", "medium", "campaign", "device")
    for session in AnalyticsSession.objects.filter(started_at__gte=start, started_at__lt=end):
        key = tuple(getattr(session, field) for field in fields)
        row = rows[key]
        row["sessions"] += 1
        row["visitor_hashes"].add(session.visitor_hash)
        row["product_views"] += int(session.viewed_product)
        row["cart_additions"] += int(session.added_to_cart)
        row["checkout_starts"] += int(session.started_checkout)
        row["delivery_selections"] += int(session.selected_delivery)
        row["payment_starts"] += int(session.started_payment)
    for conversion in AnalyticsConversion.objects.select_related("session").filter(
        approved_at__gte=start,
        approved_at__lt=end,
        session_id__isnull=False,
    ):
        session = conversion.session
        key = tuple(getattr(session, field) for field in fields)
        rows[key]["paid_orders"] += 1
        rows[key]["attributed_revenue"] += conversion.total
    return rows


@transaction.atomic
def rollup_analytics_day(day):
    start, end = _day_bounds(day)
    products = _product_rows(start, end)
    channels = _channel_rows(start, end)
    AnalyticsDailyProduct.objects.filter(day=day).delete()
    AnalyticsDailyChannel.objects.filter(day=day).delete()
    AnalyticsDailyProduct.objects.bulk_create(
        [
            AnalyticsDailyProduct(day=day, product_id=product_id, **values)
            for product_id, values in products.items()
        ]
    )
    AnalyticsDailyChannel.objects.bulk_create(
        [
            AnalyticsDailyChannel(
                day=day,
                source=key[0],
                medium=key[1],
                campaign=key[2],
                device=key[3],
                visitors=len(values.pop("visitor_hashes")),
                **values,
            )
            for key, values in channels.items()
        ]
    )
    invalidate_web_analytics()
    invalidate_commercial_analytics()
    return RollupResult(day=day, products=len(products), channels=len(channels))


def purge_expired_analytics(*, now=None):
    checked_at = now or timezone.now()
    event_cutoff = checked_at - timedelta(days=settings.ANALYTICS_EVENT_RETENTION_DAYS)
    aggregate_cutoff = checked_at - timedelta(
        days=settings.ANALYTICS_AGGREGATE_RETENTION_DAYS
    )
    aggregate_day = timezone.localdate(aggregate_cutoff)
    events, _ = AnalyticsEvent.objects.filter(occurred_at__lt=event_cutoff).delete()
    sessions, _ = AnalyticsSession.objects.filter(started_at__lt=aggregate_cutoff).delete()
    products, _ = AnalyticsDailyProduct.objects.filter(day__lt=aggregate_day).delete()
    channels, _ = AnalyticsDailyChannel.objects.filter(day__lt=aggregate_day).delete()
    return {
        "events": events,
        "sessions": sessions,
        "daily_products": products,
        "daily_channels": channels,
    }


@shared_task
def reconcile_missing_conversions():
    from analytics.services import record_paid_conversion
    from commerce.models import PaymentTransaction

    transactions = PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.APPROVED,
        analytics_conversion__isnull=True,
        order__analytics_attribution__isnull=False,
    ).select_related("order")
    count = 0
    for payment_transaction in transactions:
        count += record_paid_conversion(
            order=payment_transaction.order,
            transaction=payment_transaction,
        ) is not None
    return count


@shared_task
def rollup_recent_analytics(*, now=None):
    today = timezone.localdate(now or timezone.now())
    results = [rollup_analytics_day(today - timedelta(days=offset)) for offset in range(7)]
    return [
        {
            "day": result.day.isoformat(),
            "products": result.products,
            "channels": result.channels,
        }
        for result in results
    ]


@shared_task
def purge_expired_analytics_task():
    return purge_expired_analytics()
