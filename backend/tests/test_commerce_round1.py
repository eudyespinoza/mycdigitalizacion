from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.test_commerce_domain import make_variant


@pytest.mark.django_db
def test_authenticated_user_has_one_cart_and_atomic_line_adds_accumulate(django_user_model):
    from commerce.models import Cart
    from commerce.services import add_cart_line, get_or_create_user_cart

    user = django_user_model.objects.create_user(email="one-cart@example.test")
    cart = get_or_create_user_cart(user=user)
    with pytest.raises(IntegrityError), transaction.atomic():
        Cart.objects.create(user=user)

    variant = make_variant(sku="ATOMIC-ADD")
    add_cart_line(cart=cart, variant=variant, quantity=1)
    add_cart_line(cart=cart, variant=variant, quantity=2)
    assert cart.lines.get().quantity == 3


@pytest.mark.django_db
def test_merge_carts_locks_and_preserves_all_quantities(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import merge_carts

    user = django_user_model.objects.create_user(email="merge-safe@example.test")
    variant = make_variant(sku="MERGE-SAFE")
    destination = Cart.objects.create(user=user)
    CartLine.objects.create(cart=destination, variant=variant, quantity=2)
    anonymous = Cart.objects.create()
    CartLine.objects.create(cart=anonymous, variant=variant, quantity=3)

    merged = merge_carts(anonymous_cart=anonymous, user=user)

    assert merged.pk == destination.pk
    assert merged.lines.get().quantity == 5
    assert not Cart.objects.filter(pk=anonymous.pk).exists()


@pytest.mark.django_db
def test_expired_reservation_cannot_be_created_or_consumed_after_stock_is_reused():
    from commerce.models import StockReservation
    from commerce.services import consume_reservation, create_reservation

    variant = make_variant(sku="EXPIRED-REGRESSION", on_hand=5)
    now = timezone.now()
    with pytest.raises(ValidationError, match="future"):
        create_reservation(
            variant=variant,
            quantity=5,
            reference="past",
            expires_at=now - timezone.timedelta(seconds=1),
        )
    expired = StockReservation.objects.create(
        variant=variant,
        quantity=5,
        reference="legacy-expired",
        expires_at=now - timezone.timedelta(seconds=1),
    )
    current = create_reservation(variant=variant, quantity=5, reference="current")

    consume_reservation(expired)

    expired.refresh_from_db()
    variant.refresh_from_db()
    assert expired.status == "released"
    assert current.status == "active"
    assert variant.on_hand == 5
    assert variant.available_stock == 0


def pending_order(cart, *, at=None):
    from commerce.services import create_pending_identity_order

    return create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": cart.user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
        at=at,
    )


@pytest.mark.django_db
def test_coupon_discount_is_allocated_to_items_and_reconciles_order_total(django_user_model):
    from commerce.models import Cart, CartLine, Coupon

    user = django_user_model.objects.create_user(email="reconcile@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="RECONCILE"), quantity=1)
    now = timezone.now()
    cart.coupon = Coupon.objects.create(
        code="RECONCILE10",
        discount_type="fixed",
        value=Decimal("10"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    cart.save(update_fields=["coupon"])

    order = pending_order(cart, at=now)
    item = order.items.get()

    assert item.discount_snapshot == Decimal("10.00")
    assert item.line_total_snapshot == Decimal("90.00")
    assert sum(item.line_total_snapshot for item in order.items.all()) == order.total_snapshot


@pytest.mark.django_db
def test_coupon_cent_allocation_is_deterministic_across_multiple_lines(django_user_model):
    from commerce.models import Cart, CartLine, Coupon

    user = django_user_model.objects.create_user(email="cent-allocation@example.test")
    cart = Cart.objects.create(user=user)
    first = CartLine.objects.create(
        cart=cart, variant=make_variant(sku="CENT-A", price="1.00"), quantity=1
    )
    second = CartLine.objects.create(
        cart=cart, variant=make_variant(sku="CENT-B", price="1.00"), quantity=1
    )
    now = timezone.now()
    cart.coupon = Coupon.objects.create(
        code="ONECENT",
        discount_type="fixed",
        value=Decimal("0.01"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    cart.save(update_fields=["coupon"])

    order = pending_order(cart, at=now)
    items = {item.variant_id: item for item in order.items.all()}

    assert items[first.variant_id].discount_snapshot == Decimal("0.01")
    assert items[second.variant_id].discount_snapshot == Decimal("0.00")
    assert sum(item.line_total_snapshot for item in items.values()) == Decimal("1.99")


@pytest.mark.django_db
def test_one_pricing_timestamp_controls_promotion_snapshot(django_user_model):
    from commerce.models import Cart, CartLine, PromotionRule

    user = django_user_model.objects.create_user(email="schedule-snapshot@example.test")
    variant = make_variant(sku="SCHEDULE-SNAPSHOT")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    boundary = timezone.now()
    promotion = PromotionRule.objects.create(
        name="Boundary",
        discount_type="fixed",
        value=Decimal("5"),
        starts_at=boundary - timezone.timedelta(hours=1),
        ends_at=boundary,
    )
    promotion.products.add(variant.product)

    at_boundary = pending_order(cart, at=boundary)
    after_boundary = pending_order(cart, at=boundary + timezone.timedelta(microseconds=1))

    assert at_boundary.items.get().discount_snapshot == Decimal("5.00")
    assert after_boundary.items.get().discount_snapshot == Decimal("0.00")


@pytest.mark.django_db
def test_order_status_transition_is_audited_and_snapshots_are_immutable(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import transition_order_status

    user = django_user_model.objects.create_user(email="transition@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="TRANSITION"), quantity=1)
    order = pending_order(cart)
    order.coupon_code_snapshot = "MUTATED"
    with pytest.raises(ValidationError, match="immutable"):
        order.save()

    transitioned = transition_order_status(
        order=order, field="payment_status", value="pending", actor=user
    )
    assert transitioned.payment_status == "pending"
    assert transitioned.audit_events.filter(kind="payment_status_changed").exists()


@pytest.mark.django_db
def test_append_only_admin_and_logistics_permissions_forbid_mutation(rf):
    from django.contrib.auth.models import Group

    from commerce.admin import InventoryMovementAdmin, OrderAdmin
    from commerce.models import InventoryMovement, Order

    movement_admin = InventoryMovementAdmin(InventoryMovement, AdminSite())
    order_admin = OrderAdmin(Order, AdminSite())
    request = rf.get("/admin/")
    assert not movement_admin.has_add_permission(request)
    assert not movement_admin.has_change_permission(request)
    assert not movement_admin.has_delete_permission(request)
    assert {
        "customer_snapshot",
        "address_snapshot",
        "fiscal_snapshot",
        "coupon_code_snapshot",
        "subtotal_snapshot",
        "discount_snapshot",
        "total_snapshot",
        "identity_status",
        "payment_status",
        "fulfillment_status",
    } <= set(order_admin.get_readonly_fields(request))
    logistics = Group.objects.get(name="Orders/Logistics")
    assert not logistics.permissions.filter(
        codename__in=("change_order", "delete_inventorymovement", "add_orderauditevent")
    ).exists()


@pytest.mark.django_db
def test_order_snapshots_and_audit_records_are_append_only(django_user_model):
    from commerce.models import Cart, CartLine, InventoryMovement

    user = django_user_model.objects.create_user(email="append-only@example.test")
    variant = make_variant(sku="APPEND-ONLY")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = pending_order(cart)
    item = order.items.get()
    audit = order.audit_events.get(kind="created_pending_identity")
    movement = InventoryMovement.objects.create(
        variant=variant,
        kind="adjustment",
        quantity_delta=1,
        reference="synthetic-adjustment",
    )

    for record in (item, audit, movement):
        with pytest.raises(ValidationError, match="append-only"):
            record.save()
        with pytest.raises(ValidationError, match="append-only"):
            record.delete()
