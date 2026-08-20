from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomerProfile, Profile
from commerce.models import Order, OrderAuditEvent, PackageBox
from locations.models import Address

pytestmark = pytest.mark.django_db


def management_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="operations-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(owner)
    return client, owner


def create_customer(django_user_model):
    user = django_user_model.objects.create_user(
        email="cliente@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    Profile.objects.create(user=user, first_name="Ana", last_name="Pérez", phone="1122334455")
    profile = CustomerProfile.objects.create(user=user, consent_version="v1")
    profile.set_dni("30123456")
    profile.save()
    Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. Siempre Viva 742",
        normalized_address="Avenida Siempre Viva 742",
        street="Avenida Siempre Viva",
        number="742",
        postal_code="1000",
        locality="Ciudad Autónoma de Buenos Aires",
        province="Ciudad Autónoma de Buenos Aires",
        needs_review=False,
    )
    return user


def create_order(user):
    return Order.objects.create(
        user=user,
        identity_status=Order.IdentityStatus.VERIFIED,
        payment_status=Order.PaymentStatus.FAILED,
        fulfillment_status=Order.FulfillmentStatus.UNFULFILLED,
        fulfillment_method=Order.FulfillmentMethod.SHIPPING,
        customer_snapshot={"email": user.email, "name": "Ana Pérez"},
        address_snapshot={"street": "Avenida Siempre Viva", "number": "742"},
        fiscal_snapshot={"legal_name": "Ana Pérez", "masked_cuit": ""},
        subtotal_snapshot=Decimal("10000.00"),
        discount_snapshot=Decimal("0.00"),
        shipping_amount_snapshot=Decimal("2500.00"),
        total_snapshot=Decimal("12500.00"),
    )


def test_management_order_list_detail_and_guarded_cancel(django_user_model):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    client, owner = management_client(django_user_model)

    listed = client.get("/api/v1/management/orders/?search=cliente")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["results"][0]["customer"]["email"] == customer.email

    detail = client.get(f"/api/v1/management/orders/{order.public_id}/")
    assert detail.status_code == 200
    assert detail.json()["total"] == "12500.00"
    assert "staff_diagnostics" not in str(detail.json())

    cancelled = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {"action": "cancel", "reason": "El cliente solicitó la cancelación"},
        format="json",
    )
    assert cancelled.status_code == 200
    order.refresh_from_db()
    assert order.fulfillment_status == Order.FulfillmentStatus.CANCELLED
    assert OrderAuditEvent.objects.filter(order=order, actor=owner, kind="admin_cancelled").exists()


def test_management_order_action_requires_reason(django_user_model):
    order = create_order(create_customer(django_user_model))
    client, _ = management_client(django_user_model)

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {"action": "cancel", "reason": ""},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "reason_required"


def test_management_customer_list_masks_identity_and_includes_addresses(django_user_model):
    customer = create_customer(django_user_model)
    create_order(customer)
    client, _ = management_client(django_user_model)

    listed = client.get("/api/v1/management/customers/?search=ana")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["results"][0]["masked_dni"].endswith("3456")
    assert "30123456" not in str(listed.json())

    detail = client.get(f"/api/v1/management/customers/{customer.pk}/")
    assert detail.status_code == 200
    assert detail.json()["addresses"][0]["label"] == "Casa"
    assert detail.json()["orders"][0]["total"] == "12500.00"


def test_management_shipping_boxes_are_configurable_and_audited(django_user_model):
    client, owner = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/shipping/boxes/",
        {
            "code": "CAJA-M",
            "inner_length_cm": "30.00",
            "inner_width_cm": "20.00",
            "inner_height_cm": "15.00",
            "tare_weight_grams": 250,
            "max_weight_grams": 10000,
            "enabled": True,
        },
        format="json",
    )
    assert created.status_code == 201
    box = PackageBox.objects.get(code="CAJA-M")

    updated = client.patch(
        f"/api/v1/management/shipping/boxes/{box.pk}/",
        {"enabled": False},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert owner.management_audit_events.filter(
        resource="package_box", object_reference=str(box.pk)
    ).count() == 2


def test_customer_cannot_access_management_operations(django_user_model):
    customer = create_customer(django_user_model)
    client = APIClient()
    client.force_login(customer)
    assert client.get("/api/v1/management/orders/").status_code == 403
    assert client.get("/api/v1/management/customers/").status_code == 403
    assert client.get("/api/v1/management/shipping/boxes/").status_code == 403
