from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomerProfile, Profile
from backoffice.models import ManagementAuditEvent
from commerce.models import Order, OrderAuditEvent, PackageBox, PaymentTransaction, Refund
from locations.models import Address
from providers import ProviderUnavailable

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


def test_management_paid_order_cancellation_refunds_mercadopago_before_cancelling(
    django_user_model, monkeypatch
):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    order.payment_status = Order.PaymentStatus.PAID
    order._save_status_transition(field="payment_status")
    payment = PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-12500",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    client, owner = management_client(django_user_model)

    class ApprovedRefundAdapter:
        def refund(self, payment_id, *, amount, idempotency_key):
            assert payment_id == "mp-payment-12500"
            assert amount is None
            assert idempotency_key
            return {"id": "mp-refund-12500", "status": "approved"}

    monkeypatch.setattr(
        "backoffice.operations_views.get_payment_adapter",
        lambda: ApprovedRefundAdapter(),
    )

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {
            "action": "cancel",
            "reason": "El cliente solicitó cancelar la compra",
            "confirm_refund": True,
        },
        format="json",
    )

    assert response.status_code == 200
    order.refresh_from_db()
    payment.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.REFUNDED
    assert order.fulfillment_status == Order.FulfillmentStatus.CANCELLED
    assert payment.status == PaymentTransaction.Status.REFUNDED
    assert Refund.objects.get(order=order).provider_refund_id == "mp-refund-12500"
    assert order.audit_events.filter(kind="admin_refund_completed", actor=owner).count() == 1
    assert order.audit_events.filter(kind="admin_cancelled", actor=owner).count() == 1


def test_management_paid_order_cancellation_persists_pending_refund_and_can_retry(
    django_user_model, monkeypatch
):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    order.payment_status = Order.PaymentStatus.PAID
    order._save_status_transition(field="payment_status")
    PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-pending",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    client, _ = management_client(django_user_model)

    class PendingThenApprovedRefundAdapter:
        calls = 0

        def refund(self, payment_id, *, amount, idempotency_key):
            self.calls += 1
            return {
                "id": "mp-refund-pending",
                "status": "pending" if self.calls == 1 else "approved",
            }

    adapter = PendingThenApprovedRefundAdapter()
    monkeypatch.setattr(
        "backoffice.operations_views.get_payment_adapter",
        lambda: adapter,
    )
    payload = {
        "action": "cancel",
        "reason": "El cliente solicitó cancelar la compra",
        "confirm_refund": True,
    }

    pending = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        payload,
        format="json",
    )

    assert pending.status_code == 409
    assert pending.json()["code"] == "refund_pending"
    order.refresh_from_db()
    persisted_refund = Refund.objects.get(order=order)
    assert persisted_refund.provider_refund_id == "mp-refund-pending"
    assert persisted_refund.status == "pending"
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.fulfillment_status == Order.FulfillmentStatus.UNFULFILLED

    completed = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        payload,
        format="json",
    )

    assert completed.status_code == 200
    order.refresh_from_db()
    persisted_refund.refresh_from_db()
    assert Refund.objects.filter(order=order).count() == 1
    assert persisted_refund.status == "approved"
    assert order.payment_status == Order.PaymentStatus.REFUNDED
    assert order.fulfillment_status == Order.FulfillmentStatus.CANCELLED


def test_management_cancel_resolves_payment_adapter_after_locked_order_refresh(
    django_user_model, monkeypatch
):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-race",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    client, _ = management_client(django_user_model)

    class ApprovedRefundAdapter:
        def refund(self, payment_id, *, amount, idempotency_key):
            return {"id": "mp-refund-race", "status": "approved"}

    monkeypatch.setattr(
        "backoffice.operations_views.get_payment_adapter",
        lambda: ApprovedRefundAdapter(),
    )
    from backoffice import operations_views
    from commerce.admin_services import perform_order_admin_action as real_action

    def webhook_raced_action(**kwargs):
        raced_order = kwargs["order"]
        raced_order.payment_status = Order.PaymentStatus.PAID
        raced_order._save_status_transition(field="payment_status")
        return real_action(**kwargs)

    monkeypatch.setattr(
        operations_views,
        "perform_order_admin_action",
        webhook_raced_action,
    )

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {
            "action": "cancel",
            "reason": "El cliente solicitó cancelar la compra",
            "confirm_refund": True,
        },
        format="json",
    )

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.REFUNDED
    assert order.fulfillment_status == Order.FulfillmentStatus.CANCELLED


def test_management_paid_order_cancellation_returns_safe_provider_error(
    django_user_model, monkeypatch
):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    order.payment_status = Order.PaymentStatus.PAID
    order._save_status_transition(field="payment_status")
    PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-offline",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    client, _ = management_client(django_user_model)

    class UnavailableRefundAdapter:
        def refund(self, payment_id, *, amount, idempotency_key):
            raise ProviderUnavailable(
                "Mercado Pago no está disponible",
                diagnostics="upstream timeout with private request metadata",
            )

    monkeypatch.setattr(
        "backoffice.operations_views.get_payment_adapter",
        lambda: UnavailableRefundAdapter(),
    )

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {
            "action": "cancel",
            "reason": "El cliente solicitó cancelar la compra",
            "confirm_refund": True,
        },
        format="json",
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "payment_provider_unavailable",
        "detail": (
            "No pudimos comunicarnos con Mercado Pago. "
            "El pedido sigue activo; intentá nuevamente."
        ),
    }
    assert "private request metadata" not in str(response.json())
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.fulfillment_status == Order.FulfillmentStatus.UNFULFILLED
    assert not Refund.objects.filter(order=order).exists()
    failure = OrderAuditEvent.objects.get(order=order, kind="admin_refund_failed")
    assert failure.data == {
        "reason": "El cliente solicitó cancelar la compra",
        "code": "payment_provider_unavailable",
    }
    assert "private request metadata" not in str(failure.data)


def test_management_paid_order_cancellation_requires_explicit_refund_confirmation(
    django_user_model, monkeypatch
):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    order.payment_status = Order.PaymentStatus.PAID
    order._save_status_transition(field="payment_status")
    PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-confirmation",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    client, _ = management_client(django_user_model)

    class UnexpectedRefundAdapter:
        def refund(self, payment_id, *, amount, idempotency_key):
            raise AssertionError("No se debe reintegrar sin confirmación explícita")

    monkeypatch.setattr(
        "backoffice.operations_views.get_payment_adapter",
        lambda: UnexpectedRefundAdapter(),
    )

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {"action": "cancel", "reason": "El cliente solicitó cancelar la compra"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "paid_order_confirmation_required"
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.fulfillment_status == Order.FulfillmentStatus.UNFULFILLED
    assert not Refund.objects.filter(order=order).exists()


def test_paid_order_cancellation_requires_cancel_and_refund_permissions(django_user_model):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    order.payment_status = Order.PaymentStatus.PAID
    order._save_status_transition(field="payment_status")
    PaymentTransaction.objects.create(
        order=order,
        provider="mercadopago",
        payment_id="mp-payment-permission",
        amount=Decimal("12500.00"),
        status=PaymentTransaction.Status.APPROVED,
        provider_status="approved",
        approved_at=timezone.now(),
    )
    operator = django_user_model.objects.create_user(
        email="cancel-only@example.test",
        password="StrongPassword!2026",
        is_staff=True,
    )
    operator.user_permissions.add(Permission.objects.get(codename="cancel_order"))
    client = APIClient()
    client.force_login(operator)

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {
            "action": "cancel",
            "reason": "El cliente solicitó cancelar la compra",
            "confirm_refund": True,
        },
        format="json",
    )

    assert response.status_code == 403
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.fulfillment_status == Order.FulfillmentStatus.UNFULFILLED


def test_customer_cannot_invoke_management_order_cancellation(django_user_model):
    customer = create_customer(django_user_model)
    order = create_order(customer)
    client = APIClient()
    client.force_login(customer)

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {"action": "cancel", "reason": "Quiero cancelar la compra"},
        format="json",
    )

    assert response.status_code == 403
    order.refresh_from_db()
    assert order.fulfillment_status == Order.FulfillmentStatus.UNFULFILLED


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


def test_management_customer_contact_can_be_updated_and_is_audited(django_user_model):
    customer = create_customer(django_user_model)
    client, owner = management_client(django_user_model)

    updated = client.patch(
        f"/api/v1/management/customers/{customer.pk}/",
        {
            "first_name": "Eudys",
            "last_name": "Espinoza",
            "email": "eudys@example.test",
            "phone": "1134567890",
        },
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Eudys Espinoza"
    assert updated.json()["first_name"] == "Eudys"
    assert updated.json()["last_name"] == "Espinoza"
    assert updated.json()["email"] == "eudys@example.test"
    assert updated.json()["phone"] == "1134567890"
    customer.refresh_from_db()
    assert customer.email == "eudys@example.test"
    assert customer.profile.first_name == "Eudys"
    assert ManagementAuditEvent.objects.filter(
        actor=owner,
        action="customer.updated",
        resource="customer",
        object_reference=str(customer.pk),
    ).exists()


def test_management_customer_dni_can_be_corrected_and_is_audited(django_user_model):
    customer = create_customer(django_user_model)
    client, owner = management_client(django_user_model)

    updated = client.patch(
        f"/api/v1/management/customers/{customer.pk}/",
        {"dni": "32129876"},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["masked_dni"] == "••••9876"
    customer.customer_profile.refresh_from_db()
    assert customer.customer_profile.get_dni() == "32129876"
    event = ManagementAuditEvent.objects.get(
        actor=owner,
        action="customer.updated",
        resource="customer",
        object_reference=str(customer.pk),
    )
    assert "dni" in event.metadata["changed_fields"]


def test_management_customer_address_can_be_updated_and_is_audited(django_user_model):
    customer = create_customer(django_user_model)
    address = customer.addresses.get()
    client, owner = management_client(django_user_model)

    updated = client.patch(
        f"/api/v1/management/customers/{customer.pk}/addresses/{address.pk}/",
        {
            "label": "Depósito",
            "raw_address": "Avenida Corrientes 1550",
            "normalized_address": "Avenida Corrientes 1550",
            "street": "Avenida Corrientes",
            "number": "1550",
            "postal_code": "1042",
            "cpa": "C1042ABC",
            "locality": "Ciudad Autónoma de Buenos Aires",
            "province": "Ciudad Autónoma de Buenos Aires",
            "floor": "4",
            "apartment": "B",
            "reference": "Portón azul",
            "notes": "Llamar al llegar",
            "needs_review": False,
        },
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["label"] == "Depósito"
    assert updated.json()["number"] == "1550"
    assert updated.json()["floor"] == "4"
    assert updated.json()["cpa"] == "C1042ABC"
    assert updated.json()["notes"] == "Llamar al llegar"
    address.refresh_from_db()
    assert address.raw_address == "Avenida Corrientes 1550"
    assert ManagementAuditEvent.objects.filter(
        actor=owner,
        action="customer.address.updated",
        resource="customer",
        object_reference=str(customer.pk),
        metadata__address_id=address.pk,
    ).exists()


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
