from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone


def make_variant(*, sku="SYN-001", price="100.00", cost="40.00", on_hand=10):
    from catalog.models import Category, Product, ProductVariant
    from catalog.services import activate_product

    category, _ = Category.objects.get_or_create(name="Sintetica", slug="sintetica")
    product = Product.objects.create(
        category=category, name=f"Producto {sku}", slug=f"producto-{sku.lower()}"
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku=sku,
        price=Decimal(price),
        cost=Decimal(cost),
        packaged_weight_grams=500,
        length_cm=Decimal("10"),
        width_cm=Decimal("10"),
        height_cm=Decimal("10"),
        on_hand=on_hand,
    )
    activate_product(product=product)
    product.refresh_from_db()
    return variant


@pytest.mark.django_db
def test_best_automatic_promotion_wins_without_stacking():
    from commerce.models import PromotionRule
    from commerce.services import best_automatic_discount

    variant = make_variant(price="100.00")
    now = timezone.now()
    fixed = PromotionRule.objects.create(
        name="Sintetica fija",
        discount_type="fixed",
        value=Decimal("15.00"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    percentage = PromotionRule.objects.create(
        name="Sintetica porcentaje",
        discount_type="percentage",
        value=Decimal("20.00"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    fixed.products.add(variant.product)
    percentage.categories.add(variant.product.category)

    assert best_automatic_discount(variant=variant, quantity=2, at=now) == Decimal("40.00")


@pytest.mark.django_db
def test_non_combinable_coupon_replaces_automatic_discount_only_when_better():
    from commerce.models import Cart, CartLine, Coupon, PromotionRule
    from commerce.services import calculate_cart_totals

    variant = make_variant(price="100.00")
    cart = Cart.objects.create()
    CartLine.objects.create(cart=cart, variant=variant, quantity=2)
    now = timezone.now()
    promotion = PromotionRule.objects.create(
        name="Automatica 10",
        discount_type="percentage",
        value=Decimal("10.00"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    promotion.products.add(variant.product)
    coupon = Coupon.objects.create(
        code="SYNTHETIC25",
        discount_type="fixed",
        value=Decimal("25.00"),
        combinable=False,
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])

    totals = calculate_cart_totals(cart, at=now)

    assert totals.subtotal == Decimal("200.00")
    assert totals.discount == Decimal("25.00")
    assert totals.total == Decimal("175.00")


@pytest.mark.django_db
def test_cart_totals_are_recalculated_from_current_variant_prices():
    from commerce.models import Cart, CartLine
    from commerce.services import calculate_cart_totals

    variant = make_variant(price="123.45")
    cart = Cart.objects.create()
    CartLine.objects.create(cart=cart, variant=variant, quantity=3)

    totals = calculate_cart_totals(cart)

    assert totals.subtotal == Decimal("370.35")
    assert totals.discount == Decimal("0.00")
    assert totals.total == Decimal("370.35")


@pytest.mark.django_db
def test_reservation_rejects_insufficient_available_stock():
    from commerce.services import InsufficientStock, create_reservation

    variant = make_variant(on_hand=2)

    with pytest.raises(InsufficientStock):
        create_reservation(variant=variant, quantity=3, reference="synthetic-cart")


@pytest.mark.django_db
def test_available_stock_excludes_only_active_unexpired_reservations():
    from commerce.services import create_reservation, release_reservation

    variant = make_variant(sku="SYN-AVAILABLE", on_hand=7)
    reservation = create_reservation(
        variant=variant, quantity=3, reference="synthetic-available"
    )
    assert variant.available_stock == 4

    release_reservation(reservation)
    assert variant.available_stock == 7


@pytest.mark.django_db
def test_reservation_consumption_and_release_are_idempotent():
    from commerce.models import InventoryMovement
    from commerce.services import consume_reservation, create_reservation, release_reservation

    first = create_reservation(
        variant=make_variant(sku="SYN-CONSUME", on_hand=5),
        quantity=2,
        reference="synthetic-consume",
    )
    consume_reservation(first)
    consume_reservation(first)
    assert InventoryMovement.objects.filter(reservation=first, kind="sale").count() == 1

    second = create_reservation(
        variant=make_variant(sku="SYN-RELEASE", on_hand=5),
        quantity=2,
        reference="synthetic-release",
    )
    release_reservation(second)
    release_reservation(second)
    assert InventoryMovement.objects.filter(reservation=second, kind="release").count() == 1


@pytest.mark.django_db
def test_order_creation_persists_customer_address_fiscal_item_and_price_snapshots(
    django_user_model,
):
    from commerce.models import Cart, CartLine
    from commerce.services import create_pending_identity_order

    user = django_user_model.objects.create_user(email="buyer@example.test")
    variant = make_variant(price="149.99", cost="80.00")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=2)

    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={"street": "Calle Sintetica", "number": "123"},
        fiscal_snapshot={"condition": "consumidor_final"},
        fulfillment_method="shipping",
    )

    item = order.items.get()
    assert order.identity_status == "pending_identity"
    assert order.customer_snapshot == {"email": "buyer@example.test"}
    assert order.address_snapshot["street"] == "Calle Sintetica"
    assert order.fiscal_snapshot == {"condition": "consumidor_final"}
    assert item.sku_snapshot == "SYN-001"
    assert item.unit_price_snapshot == Decimal("149.99")
    assert item.discount_snapshot == Decimal("0.00")
    assert not order.reservations.exists()


@pytest.mark.django_db
def test_cart_rejects_a_second_coupon():
    from commerce.models import Cart, Coupon
    from commerce.services import apply_coupon

    now = timezone.now()
    cart = Cart.objects.create()
    first = Coupon.objects.create(
        code="FIRST",
        discount_type="fixed",
        value=Decimal("1"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    second = Coupon.objects.create(
        code="SECOND",
        discount_type="fixed",
        value=Decimal("2"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    apply_coupon(cart, first.code, at=now)

    with pytest.raises(ValidationError, match="one coupon"):
        apply_coupon(cart, second.code, at=now)


@pytest.mark.django_db
def test_order_snapshots_the_applied_coupon_code(django_user_model):
    from commerce.models import Cart, CartLine, Coupon
    from commerce.services import create_pending_identity_order

    user = django_user_model.objects.create_user(email="coupon-buyer@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=make_variant(sku="SYN-COUPON"), quantity=1)
    now = timezone.now()
    cart.coupon = Coupon.objects.create(
        code="SNAPSHOT10",
        discount_type="fixed",
        value=Decimal("10"),
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=1),
    )
    cart.save(update_fields=["coupon"])

    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )

    assert order.coupon_code_snapshot == "SNAPSHOT10"
    assert order.discount_snapshot == Decimal("10.00")
