from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from commerce.models import Order

pytestmark = pytest.mark.django_db


def test_management_product_list_has_a_constant_query_budget(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="performance-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    category = Category.objects.create(name="Rendimiento", slug="rendimiento")
    for number in range(30):
        product = Product.objects.create(
            category=category,
            name=f"Producto gestión {number:02d}",
            slug=f"producto-gestion-{number:02d}",
        )
        ProductVariant.objects.create(
            product=product,
            sku=f"MGMT-{number:03d}",
            price=Decimal("100.00"),
            cost=Decimal("50.00"),
            packaged_weight_grams=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("2"),
            on_hand=5,
        )

    client = APIClient()
    client.force_login(owner)
    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/v1/management/products/?page_size=30")

    assert response.status_code == 200
    assert response.json()["count"] == 30
    assert len(captured) <= 10


def test_management_order_list_does_not_prefetch_detail_relations(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="orders-performance-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    for number in range(30):
        Order.objects.create(
            user=owner,
            fulfillment_method=Order.FulfillmentMethod.PICKUP,
            customer_snapshot={"name": f"Cliente {number}", "email": owner.email},
            address_snapshot={},
            fiscal_snapshot={},
            subtotal_snapshot=Decimal("100.00"),
            discount_snapshot=Decimal("0.00"),
            shipping_amount_snapshot=Decimal("0.00"),
            total_snapshot=Decimal("100.00"),
        )

    client = APIClient()
    client.force_login(owner)
    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/v1/management/orders/?page_size=30")

    assert response.status_code == 200
    assert response.json()["count"] == 30
    assert len(captured) <= 6


def test_management_analytics_have_bounded_empty_period_query_budgets(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="analytics-performance-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    today = timezone.localdate()
    period = f"from={today.isoformat()}&to={(today + timezone.timedelta(days=1)).isoformat()}"
    client = APIClient()
    client.force_login(owner)

    with CaptureQueriesContext(connection) as web_queries:
        web = client.get(f"/api/v1/management/analytics/web/?{period}")
    with CaptureQueriesContext(connection) as commercial_queries:
        commercial = client.get(f"/api/v1/management/analytics/commercial/?{period}")

    assert web.status_code == 200
    assert commercial.status_code == 200
    assert len(web_queries) <= 24
    assert len(commercial_queries) <= 24
