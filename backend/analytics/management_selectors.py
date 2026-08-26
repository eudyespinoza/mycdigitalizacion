import math
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Min, Sum
from django.utils import timezone

from analytics.models import AnalyticsConversion, AnalyticsEvent, AnalyticsSession
from catalog.models import ProductVariant
from commerce.models import OrderItem, PaymentTransaction, Refund, StockReservation

ZERO = Decimal("0")


def _bounds(start, end):
    zone = ZoneInfo(settings.TIME_ZONE)
    return (
        datetime.combine(start, time.min, tzinfo=zone),
        datetime.combine(end, time.min, tzinfo=zone),
    )


def _money(value):
    return f"{Decimal(value or 0):.2f}"


def _rate(numerator, denominator):
    if not denominator:
        return None
    return f"{Decimal(numerator) * 100 / Decimal(denominator):.2f}"


def _step(count, denominator):
    return {
        "count": count,
        "rate": _rate(count, denominator),
        "has_denominator": bool(denominator),
    }


def _period(start, end):
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "timezone": settings.TIME_ZONE,
    }


def _date_rows(start, end):
    return [start + timedelta(days=offset) for offset in range((end - start).days)]


def web_dashboard(*, start, end, compare=False):
    start_at, end_at = _bounds(start, end)
    sessions = AnalyticsSession.objects.filter(started_at__gte=start_at, started_at__lt=end_at)
    session_ids = list(sessions.values_list("pk", flat=True))
    session_count = len(session_ids)
    visitor_count = sessions.values("visitor_hash").distinct().count()
    converted_ids = set(
        AnalyticsConversion.objects.filter(session_id__in=session_ids).values_list(
            "session_id", flat=True
        )
    )
    conversions = AnalyticsConversion.objects.filter(session_id__in=session_ids)
    attributed_orders = conversions.count()
    attributed_revenue = conversions.aggregate(total=Sum("total"))["total"] or ZERO
    product_count = sessions.filter(viewed_product=True).count()
    cart_count = sessions.filter(added_to_cart=True).count()
    checkout_count = sessions.filter(started_checkout=True).count()
    delivery_count = sessions.filter(selected_delivery=True).count()
    payment_count = sessions.filter(started_payment=True).count()
    mature_cutoff = timezone.now() - timedelta(hours=24)
    mature_checkout = sessions.filter(started_checkout=True, started_at__lte=mature_cutoff)
    mature_count = mature_checkout.count()
    mature_converted = mature_checkout.filter(pk__in=converted_ids).count()

    all_paid = PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.APPROVED,
        approved_at__gte=start_at,
        approved_at__lt=end_at,
    )
    attributed_paid = all_paid.filter(order__analytics_attribution__isnull=False).count()
    attribution_percentage = _rate(attributed_paid, all_paid.count())

    series_by_day = {
        day: {"date": day.isoformat(), "sessions": 0, "carts": 0, "orders": 0}
        for day in _date_rows(start, end)
    }
    for session in sessions.only("started_at", "added_to_cart"):
        day = timezone.localtime(session.started_at).date()
        if day in series_by_day:
            series_by_day[day]["sessions"] += 1
            series_by_day[day]["carts"] += int(session.added_to_cart)
    for conversion in conversions.only("approved_at"):
        day = timezone.localtime(conversion.approved_at).date()
        if day in series_by_day:
            series_by_day[day]["orders"] += 1

    channel_rows = defaultdict(
        lambda: {"sessions": 0, "converted": set(), "revenue": ZERO}
    )
    device_rows = defaultdict(lambda: {"sessions": 0, "converted": set(), "revenue": ZERO})
    session_map = {}
    for session in sessions:
        session_map[session.pk] = session
        channel_key = (session.source, session.medium, session.campaign)
        channel_rows[channel_key]["sessions"] += 1
        device_rows[session.device]["sessions"] += 1
    for conversion in conversions:
        session = session_map.get(conversion.session_id)
        if session is None:
            continue
        channel_key = (session.source, session.medium, session.campaign)
        channel_rows[channel_key]["converted"].add(session.pk)
        channel_rows[channel_key]["revenue"] += conversion.total
        device_rows[session.device]["converted"].add(session.pk)
        device_rows[session.device]["revenue"] += conversion.total

    product_events = AnalyticsEvent.objects.filter(
        occurred_at__gte=start_at,
        occurred_at__lt=end_at,
        product_id__isnull=False,
    ).values("product_id", "product__name", "event_type")
    products = defaultdict(lambda: {"views": 0, "cart_additions": 0})
    product_names = {}
    for event in product_events:
        product_id = event["product_id"]
        product_names[product_id] = event["product__name"]
        if event["event_type"] == AnalyticsEvent.EventType.PRODUCT_VIEW:
            products[product_id]["views"] += 1
        elif event["event_type"] == AnalyticsEvent.EventType.ADD_TO_CART:
            products[product_id]["cart_additions"] += 1

    data_since = AnalyticsSession.objects.aggregate(value=Min("started_at"))["value"]
    report = {
        "period": _period(start, end),
        "data_since": data_since.isoformat() if data_since else None,
        "coverage": {
            "attribution_percentage": attribution_percentage,
            "has_denominator": all_paid.exists(),
        },
        "kpis": {
            "sessions": session_count,
            "visitors": visitor_count,
            "conversion_rate": _rate(len(converted_ids), session_count),
            "attributed_revenue": _money(attributed_revenue),
            "average_ticket": (
                _money(attributed_revenue / attributed_orders) if attributed_orders else None
            ),
            "checkout_abandonment": _rate(
                mature_count - mature_converted,
                mature_count,
            ),
        },
        "funnel": {
            "sessions": _step(session_count, session_count),
            "product": _step(product_count, session_count),
            "cart": _step(cart_count, product_count),
            "checkout": _step(checkout_count, cart_count),
            "delivery": _step(delivery_count, checkout_count),
            "payment": _step(payment_count, checkout_count),
            "paid": _step(len(converted_ids), payment_count),
        },
        "series": list(series_by_day.values()),
        "tables": {
            "products": [
                {
                    "product_id": product_id,
                    "name": product_names[product_id],
                    **values,
                    "cart_rate": _rate(values["cart_additions"], values["views"]),
                }
                for product_id, values in sorted(
                    products.items(), key=lambda item: (-item[1]["views"], item[0])
                )[:20]
            ],
            "channels": [
                {
                    "source": key[0] or "directo",
                    "medium": key[1],
                    "campaign": key[2],
                    "sessions": values["sessions"],
                    "conversion_rate": _rate(
                        len(values["converted"]), values["sessions"]
                    ),
                    "revenue": _money(values["revenue"]),
                }
                for key, values in sorted(
                    channel_rows.items(), key=lambda item: -item[1]["sessions"]
                )
            ],
            "devices": [
                {
                    "device": device,
                    "sessions": values["sessions"],
                    "conversion_rate": _rate(
                        len(values["converted"]), values["sessions"]
                    ),
                    "revenue": _money(values["revenue"]),
                }
                for device, values in sorted(
                    device_rows.items(), key=lambda item: -item[1]["sessions"]
                )
            ],
        },
        "comparison": None,
    }
    if compare:
        duration = end - start
        previous = web_dashboard(start=start - duration, end=start, compare=False)
        report["comparison"] = previous["kpis"]
    return report


def _commercial_source(*, start_at, end_at):
    payments = list(
        PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.APPROVED,
            approved_at__gte=start_at,
            approved_at__lt=end_at,
        ).select_related("order")
    )
    refunds = list(
        Refund.objects.filter(
            status="approved",
            updated_at__gte=start_at,
            updated_at__lt=end_at,
        ).select_related("order")
    )
    return payments, refunds


def commercial_dashboard(
    *,
    start,
    end,
    compare=False,
    category_id=None,
    brand_id=None,
    coverage_days=30,
):
    start_at, end_at = _bounds(start, end)
    payments, refunds = _commercial_source(start_at=start_at, end_at=end_at)
    paid_by_order = defaultdict(lambda: ZERO)
    for payment in payments:
        paid_by_order[payment.order_id] += payment.amount
    refund_by_order = defaultdict(lambda: ZERO)
    for refund in refunds:
        refund_by_order[refund.order_id] += refund.amount
    order_ids = set(paid_by_order)
    items = OrderItem.objects.filter(order_id__in=order_ids).select_related(
        "variant__product__category",
        "variant__product__brand",
    )
    if category_id:
        items = items.filter(variant__product__category_id=category_id)
    if brand_id:
        items = items.filter(variant__product__brand_id=brand_id)
    items = list(items)

    paid_total = sum(paid_by_order.values(), ZERO)
    refunds_total = sum(refund_by_order.values(), ZERO)
    known_revenue = ZERO
    net_product_revenue = ZERO
    gross_margin = ZERO
    net_units = ZERO
    net_discounts = ZERO
    rows = defaultdict(
        lambda: {
            "product_id": None,
            "product": "",
            "category": "",
            "units": ZERO,
            "revenue": ZERO,
            "margin": ZERO,
            "cost_covered": True,
        }
    )
    for item in items:
        paid = paid_by_order[item.order_id]
        refunded = min(refund_by_order[item.order_id], paid)
        retained_ratio = (paid - refunded) / paid if paid else ZERO
        line_revenue = item.line_total_snapshot * retained_ratio
        units = Decimal(item.quantity) * retained_ratio
        net_product_revenue += line_revenue
        net_units += units
        net_discounts += item.discount_snapshot * retained_ratio
        row = rows[item.sku_snapshot]
        row["product_id"] = item.variant.product_id if item.variant_id else None
        row["product"] = item.product_name_snapshot
        row["category"] = (
            item.variant.product.category.name if item.variant_id else "Sin categoría"
        )
        row["units"] += units
        row["revenue"] += line_revenue
        if item.unit_cost_snapshot is None:
            row["cost_covered"] = False
            continue
        margin = (
            item.line_total_snapshot
            - item.unit_cost_snapshot * Decimal(item.quantity)
        ) * retained_ratio
        known_revenue += line_revenue
        gross_margin += margin
        row["margin"] += margin

    filtered_variants = ProductVariant.objects.filter(is_active=True).select_related(
        "product__category", "product__brand"
    )
    if category_id:
        filtered_variants = filtered_variants.filter(product__category_id=category_id)
    if brand_id:
        filtered_variants = filtered_variants.filter(product__brand_id=brand_id)
    variants = list(filtered_variants)
    active_reserved = defaultdict(int)
    for reservation in StockReservation.objects.filter(
        variant_id__in=[variant.pk for variant in variants],
        status=StockReservation.Status.ACTIVE,
        tracks_inventory=True,
        expires_at__gt=timezone.now(),
    ):
        active_reserved[reservation.variant_id] += reservation.quantity
    units_by_sku = {sku: values["units"] for sku, values in rows.items()}
    period_days = max((end - start).days, 1)
    reorder = []
    no_movement = []
    inventory_value = ZERO
    for variant in variants:
        if variant.stock_is_infinite:
            continue
        available = variant.on_hand - active_reserved[variant.pk]
        inventory_value += variant.cost * available
        units = units_by_sku.get(variant.sku, ZERO)
        velocity = units / period_days
        suggested = max(math.ceil(velocity * coverage_days) - available, 0)
        coverage = Decimal(available) / velocity if velocity else None
        operational = {
            "variant_id": variant.pk,
            "sku": variant.sku,
            "product": variant.product.name,
            "stock": available,
            "sold_units": _money(units),
            "daily_velocity": _money(velocity),
            "stock_coverage_days": _money(coverage) if coverage is not None else None,
            "suggested_units": suggested,
        }
        if suggested:
            reorder.append(operational)
        if not units:
            no_movement.append(operational)

    series = {
        day: {"date": day.isoformat(), "sales": ZERO, "refunds": ZERO}
        for day in _date_rows(start, end)
    }
    for payment in payments:
        day = timezone.localtime(payment.approved_at).date()
        if day in series:
            series[day]["sales"] += payment.amount
    for refund in refunds:
        day = timezone.localtime(refund.updated_at).date()
        if day in series:
            series[day]["refunds"] += refund.amount

    all_paid_orders = len(paid_by_order)
    attributed_orders = PaymentTransaction.objects.filter(
        pk__in=[payment.pk for payment in payments],
        order__analytics_attribution__isnull=False,
    ).values("order_id").distinct().count()
    data_since = PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.APPROVED,
        approved_at__isnull=False,
    ).aggregate(value=Min("approved_at"))["value"]
    report = {
        "period": _period(start, end),
        "data_since": data_since.isoformat() if data_since else None,
        "filters": {
            "category": category_id,
            "brand": brand_id,
            "coverage_days": coverage_days,
        },
        "coverage": {
            "attribution_percentage": _rate(attributed_orders, all_paid_orders),
            "cost_percentage": _rate(known_revenue, net_product_revenue),
        },
        "kpis": {
            "net_sales": _money(paid_total - refunds_total),
            "paid_orders": all_paid_orders,
            "net_units": _money(net_units),
            "average_ticket": _money(paid_total / all_paid_orders)
            if all_paid_orders
            else None,
            "discounts": _money(net_discounts),
            "refunds": _money(refunds_total),
            "gross_product_margin": _money(gross_margin),
            "inventory_value": _money(inventory_value),
            "reorder_variants": len(reorder),
        },
        "series": [
            {
                "date": values["date"],
                "sales": _money(values["sales"]),
                "refunds": _money(values["refunds"]),
                "net_sales": _money(values["sales"] - values["refunds"]),
            }
            for values in series.values()
        ],
        "tables": {
            "skus": [
                {
                    "sku": sku,
                    **{
                        key: (_money(value) if isinstance(value, Decimal) else value)
                        for key, value in values.items()
                    },
                }
                for sku, values in sorted(
                    rows.items(), key=lambda item: (-item[1]["revenue"], item[0])
                )
            ],
            "reorder": sorted(
                reorder,
                key=lambda row: (-row["suggested_units"], row["sku"]),
            ),
            "no_movement": sorted(no_movement, key=lambda row: row["sku"]),
        },
        "comparison": None,
    }
    if compare:
        duration = end - start
        previous = commercial_dashboard(
            start=start - duration,
            end=start,
            compare=False,
            category_id=category_id,
            brand_id=brand_id,
            coverage_days=coverage_days,
        )
        report["comparison"] = previous["kpis"]
    return report
