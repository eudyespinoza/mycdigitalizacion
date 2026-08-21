import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Brand, Category, Product, ProductVariant
from commerce.models import Order

pytestmark = pytest.mark.django_db


def create_user(django_user_model, email, *, is_staff=False):
    return django_user_model.objects.create_user(
        email=email,
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
        is_staff=is_staff,
    )


def test_management_session_requires_an_active_staff_user(django_user_model):
    client = APIClient()
    anonymous = client.get("/api/v1/management/session/")
    assert anonymous.status_code == 403

    customer = create_user(django_user_model, "customer@example.test")
    client.force_login(customer)
    denied = client.get("/api/v1/management/session/")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "No tenés permiso para acceder al panel de gestión."

    staff = create_user(django_user_model, "staff@example.test", is_staff=True)
    client.force_login(staff)
    allowed = client.get("/api/v1/management/session/")
    assert allowed.status_code == 200
    assert allowed.json()["user"] == {
        "id": staff.pk,
        "email": "staff@example.test",
        "first_name": "",
        "last_name": "",
        "is_staff": True,
        "is_superuser": False,
        "permissions": [],
    }


def test_management_dashboard_reports_real_operational_counts(django_user_model):
    staff = create_user(django_user_model, "owner@example.test", is_staff=True)
    category = Category.objects.create(name="Librería", slug="libreria")
    brand = Brand.objects.create(name="myc", slug="myc")
    product = Product.objects.create(
        name="Cuaderno",
        slug="cuaderno",
        description="Cuaderno rayado",
        category=category,
        brand=brand,
    )
    ProductVariant.objects.create(
        product=product,
        sku="CUA-001",
        name="Predeterminada",
        price="1200.00",
        cost="700.00",
        on_hand=2,
        packaged_weight_grams=200,
        length_cm="21.00",
        width_cm="15.00",
        height_cm="1.00",
    )
    ProductVariant.objects.create(
        product=product,
        sku="CUA-INFINITO",
        name="A pedido",
        price="1200.00",
        cost="700.00",
        on_hand=0,
        stock_is_infinite=True,
        packaged_weight_grams=200,
        length_cm="21.00",
        width_cm="15.00",
        height_cm="1.00",
    )
    Order.objects.create(
        user=staff,
        identity_status="manual_review",
        payment_status="pending",
        fulfillment_status="unfulfilled",
        fulfillment_method="pickup",
        customer_snapshot={},
        address_snapshot={},
        fiscal_snapshot={},
        subtotal_snapshot="0.00",
        discount_snapshot="0.00",
        shipping_amount_snapshot="0.00",
        total_snapshot="0.00",
    )

    client = APIClient()
    client.force_login(staff)
    response = client.get("/api/v1/management/dashboard/")

    assert response.status_code == 200
    assert response.json()["metrics"] == {
        "active_products": 1,
        "low_stock_variants": 1,
        "orders_requiring_attention": 1,
        "integration_incidents": 0,
    }


def test_django_admin_is_not_routable(client):
    assert client.get("/admin/").status_code == 404
