import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone

from analytics.models import (
    AnalyticsConversion,
    AnalyticsOrderAttribution,
    AnalyticsSession,
)


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="analytics", codename__in=codenames)
    )


def management_user(django_user_model, *, permissions):
    user = django_user_model.objects.create_user(
        email=f"analytics-manager-{uuid.uuid4()}@example.test",
        is_staff=True,
    )
    grant(user, *permissions)
    return user


def make_variant(*, sku, cost="100.00", on_hand=20, infinite=False):
    from catalog.models import Category, Product, ProductVariant

    category, _ = Category.objects.get_or_create(name="Reportes", slug="reportes")
    product = Product.objects.create(
        category=category,
        name=f"Producto {sku}",
        slug=f"producto-{sku.casefold()}",
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku=sku,
        price=Decimal("1000.00"),
        cost=Decimal(cost),
        packaged_weight_grams=100,
        length_cm=Decimal("10"),
        width_cm=Decimal("10"),
        height_cm=Decimal("10"),
        on_hand=on_hand,
        stock_is_infinite=infinite,
    )
    return variant


def create_paid_order(
    django_user_model,
    *,
    sku,
    amount="100000.00",
    cost_snapshot="50000.00",
    quantity=1,
    refund="0",
):
    from commerce.models import Order, OrderItem, PaymentTransaction, Refund

    customer = django_user_model.objects.create_user(
        email=f"commerce-{uuid.uuid4()}@example.test"
    )
    variant = make_variant(sku=sku)
    total = Decimal(amount)
    order = Order.objects.create(
        user=customer,
        identity_status=Order.IdentityStatus.VERIFIED,
        payment_status=Order.PaymentStatus.PAID,
        fulfillment_method=Order.FulfillmentMethod.PICKUP,
        customer_snapshot={},
        address_snapshot={},
        fiscal_snapshot={},
        subtotal_snapshot=total,
        discount_snapshot=Decimal("0"),
        shipping_amount_snapshot=Decimal("0"),
        total_snapshot=total,
    )
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_name_snapshot=variant.product.name,
        variant_name_snapshot=variant.name,
        sku_snapshot=variant.sku,
        quantity=quantity,
        unit_price_snapshot=total / quantity,
        unit_cost_snapshot=(
            Decimal(cost_snapshot) if cost_snapshot is not None else None
        ),
        discount_snapshot=Decimal("0"),
        line_total_snapshot=total,
    )
    payment = PaymentTransaction.objects.create(
        order=order,
        amount=total,
        status=PaymentTransaction.Status.APPROVED,
        approved_at=timezone.now(),
    )
    if Decimal(refund):
        Refund.objects.create(
            order=order,
            transaction=payment,
            amount=Decimal(refund),
            status="approved",
        )
    return order, payment


def period_query():
    today = timezone.localdate()
    return f"from={today.isoformat()}&to={(today + timezone.timedelta(days=1)).isoformat()}"


@pytest.mark.django_db
def test_commercial_dashboard_uses_approved_payments_and_refunds(
    client,
    django_user_model,
):
    manager = management_user(
        django_user_model,
        permissions=("view_commercial_analytics",),
    )
    create_paid_order(
        django_user_model,
        sku="REPORT-1",
        amount="100000.00",
        refund="12500.00",
    )
    client.force_login(manager)

    response = client.get(f"/api/v1/management/analytics/commercial/?{period_query()}")

    assert response.status_code == 200
    assert response.json()["kpis"]["net_sales"] == "87500.00"
    assert response.json()["kpis"]["refunds"] == "12500.00"
    assert response.json()["kpis"]["paid_orders"] == 1


@pytest.mark.django_db
def test_margin_reports_partial_cost_coverage_instead_of_estimating(
    client,
    django_user_model,
):
    manager = management_user(
        django_user_model,
        permissions=("view_commercial_analytics",),
    )
    create_paid_order(
        django_user_model,
        sku="KNOWN-COST",
        amount="100.00",
        cost_snapshot="40.00",
    )
    create_paid_order(
        django_user_model,
        sku="UNKNOWN-COST",
        amount="100.00",
        cost_snapshot=None,
    )
    client.force_login(manager)

    payload = client.get(
        f"/api/v1/management/analytics/commercial/?{period_query()}"
    ).json()

    assert payload["kpis"]["gross_product_margin"] == "60.00"
    assert payload["coverage"]["cost_percentage"] == "50.00"


@pytest.mark.django_db
def test_web_dashboard_reports_funnel_and_honest_denominators(client, django_user_model):
    manager = management_user(
        django_user_model,
        permissions=("view_web_analytics",),
    )
    session = AnalyticsSession.objects.create(
        visitor_hash="f" * 64,
        source="directo",
        entry_path="/",
        viewed_product=True,
        added_to_cart=True,
    )
    order, payment = create_paid_order(django_user_model, sku="ATTRIBUTED", amount="250.00")
    AnalyticsOrderAttribution.objects.create(order=order, session=session)
    AnalyticsConversion.objects.create(
        session=session,
        order=order,
        transaction=payment,
        approved_at=payment.approved_at,
        total=order.total_snapshot,
        subtotal=order.subtotal_snapshot,
        discount=order.discount_snapshot,
        shipping=order.shipping_amount_snapshot,
    )
    client.force_login(manager)

    payload = client.get(f"/api/v1/management/analytics/web/?{period_query()}").json()

    assert payload["kpis"]["sessions"] == 1
    assert payload["kpis"]["conversion_rate"] == "100.00"
    assert payload["funnel"]["cart"]["count"] == 1
    assert payload["funnel"]["checkout"]["rate"] == "0.00"
    assert payload["funnel"]["checkout"]["has_denominator"] is True


@pytest.mark.django_db
def test_analytics_endpoints_require_the_exact_permission(client, django_user_model):
    user = management_user(django_user_model, permissions=())
    client.force_login(user)

    assert client.get(f"/api/v1/management/analytics/web/?{period_query()}").status_code == 403
    assert (
        client.get(f"/api/v1/management/analytics/commercial/?{period_query()}").status_code
        == 403
    )


@pytest.mark.django_db
def test_commercial_export_is_aggregated_and_audited(client, django_user_model):
    from backoffice.models import ManagementAuditEvent

    manager = management_user(
        django_user_model,
        permissions=("view_commercial_analytics", "export_commercial_analytics"),
    )
    create_paid_order(django_user_model, sku="CSV-SKU", amount="300.00")
    client.force_login(manager)

    response = client.get(
        f"/api/v1/management/analytics/commercial/export.csv?{period_query()}"
    )
    content = b"".join(response.streaming_content).decode("utf-8-sig")

    assert response.status_code == 200
    assert "CSV-SKU" in content
    assert "commerce-" not in content
    audit = ManagementAuditEvent.objects.get(action="analytics.commercial_exported")
    assert audit.actor == manager
    assert audit.metadata["row_count"] == 1


@pytest.mark.django_db
def test_analytics_rejects_invalid_or_excessive_ranges(client, django_user_model):
    manager = management_user(
        django_user_model,
        permissions=("view_web_analytics",),
    )
    client.force_login(manager)

    reversed_range = client.get(
        "/api/v1/management/analytics/web/?from=2026-08-20&to=2026-08-01"
    )
    excessive = client.get(
        "/api/v1/management/analytics/web/?from=2020-01-01&to=2026-08-01"
    )

    assert reversed_range.status_code == 400
    assert excessive.status_code == 400


@pytest.mark.django_db
def test_role_sync_assigns_exact_analytics_permissions():
    from django.contrib.auth.models import Group

    from config.admin_roles import sync_admin_roles

    sync_admin_roles()
    permissions_by_role = {
        group.name: set(
            group.permissions.filter(content_type__app_label="analytics").values_list(
                "codename", flat=True
            )
        )
        for group in Group.objects.filter(
            name__in=("Owner", "Content", "Catalog", "Orders/Logistics")
        )
    }

    assert permissions_by_role["Owner"] == {
        "add_analyticssession",
        "change_analyticssession",
        "delete_analyticssession",
        "view_analyticssession",
        "view_web_analytics",
        "view_commercial_analytics",
        "export_commercial_analytics",
        "add_analyticsevent",
        "change_analyticsevent",
        "delete_analyticsevent",
        "view_analyticsevent",
        "add_analyticsorderattribution",
        "change_analyticsorderattribution",
        "delete_analyticsorderattribution",
        "view_analyticsorderattribution",
        "add_analyticsconversion",
        "change_analyticsconversion",
        "delete_analyticsconversion",
        "view_analyticsconversion",
        "add_analyticsdailyproduct",
        "change_analyticsdailyproduct",
        "delete_analyticsdailyproduct",
        "view_analyticsdailyproduct",
        "add_analyticsdailychannel",
        "change_analyticsdailychannel",
        "delete_analyticsdailychannel",
        "view_analyticsdailychannel",
    }
    assert permissions_by_role["Content"] == {"view_web_analytics"}
    assert permissions_by_role["Catalog"] == {"view_commercial_analytics"}
    assert permissions_by_role["Orders/Logistics"] == {
        "view_web_analytics",
        "view_commercial_analytics",
        "export_commercial_analytics",
    }
