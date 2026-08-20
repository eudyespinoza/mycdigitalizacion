from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from catalog.models import ProductVariant
from commerce.models import (
    Cart,
    CartLine,
    Coupon,
    InventoryMovement,
    Order,
    OrderAuditEvent,
    OrderItem,
    PromotionRule,
    StockReservation,
)

MONEY = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def discount_amount(discount_type, value, amount):
    if discount_type == "percentage":
        return money(amount * value / Decimal("100"))
    return min(money(value), money(amount))


def best_automatic_discount(*, variant, quantity, at=None):
    checked_at = at or timezone.now()
    line_amount = money(variant.price * quantity)
    rules = PromotionRule.objects.filter(
        enabled=True,
        starts_at__lte=checked_at,
        ends_at__gte=checked_at,
    ).filter(Q(products=variant.product) | Q(categories=variant.product.category))
    discounts = [
        discount_amount(rule.discount_type, rule.value, line_amount)
        for rule in rules.distinct()
    ]
    return max(discounts, default=Decimal("0.00"))


@dataclass(frozen=True)
class CartTotals:
    subtotal: Decimal
    discount: Decimal
    total: Decimal


def calculate_cart_totals(cart, *, at=None):
    checked_at = at or timezone.now()
    lines = list(cart.lines.select_related("variant__product__category"))
    subtotal = money(sum((line.variant.price * line.quantity for line in lines), Decimal("0")))
    automatic_discount = money(
        sum(
            (
                best_automatic_discount(
                    variant=line.variant, quantity=line.quantity, at=checked_at
                )
                for line in lines
            ),
            Decimal("0"),
        )
    )
    discount = automatic_discount
    if cart.coupon and cart.coupon.is_active(checked_at):
        coupon_discount = discount_amount(
            cart.coupon.discount_type, cart.coupon.value, subtotal
        )
        discount = (
            money(automatic_discount + coupon_discount)
            if cart.coupon.combinable
            else max(automatic_discount, coupon_discount)
        )
    discount = min(discount, subtotal)
    return CartTotals(subtotal=subtotal, discount=discount, total=money(subtotal - discount))


def apply_coupon(cart, code, *, at=None):
    if cart.coupon_id:
        raise ValidationError("A cart accepts only one coupon")
    try:
        coupon = Coupon.objects.get(code=code.strip().upper())
    except Coupon.DoesNotExist as exc:
        raise ValidationError("Coupon is invalid") from exc
    if not coupon.is_active(at):
        raise ValidationError("Coupon is not active")
    cart.coupon = coupon
    cart.save(update_fields=["coupon", "updated_at"])
    return cart


def merge_carts(*, anonymous_cart, user):
    with transaction.atomic():
        cart, _ = Cart.objects.get_or_create(user=user)
        for source in anonymous_cart.lines.select_related("variant"):
            line, created = CartLine.objects.get_or_create(
                cart=cart, variant=source.variant, defaults={"quantity": source.quantity}
            )
            if not created:
                line.quantity += source.quantity
                line.save(update_fields=["quantity"])
        if not cart.coupon_id and anonymous_cart.coupon_id:
            cart.coupon_id = anonymous_cart.coupon_id
            cart.save(update_fields=["coupon"])
        anonymous_cart.delete()
        return cart


class InsufficientStock(ValidationError):
    pass


@transaction.atomic
def create_reservation(*, variant, quantity, reference, expires_at=None):
    if quantity < 1:
        raise ValidationError("Reservation quantity must be positive")
    locked_variant = ProductVariant.objects.select_for_update().get(pk=variant.pk)
    now = timezone.now()
    reserved = (
        StockReservation.objects.filter(
            variant=locked_variant,
            status=StockReservation.Status.ACTIVE,
            expires_at__gt=now,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    if locked_variant.on_hand - reserved < quantity:
        raise InsufficientStock("Insufficient available stock")
    reservation = StockReservation.objects.create(
        variant=locked_variant,
        quantity=quantity,
        reference=reference,
        expires_at=expires_at or now + timezone.timedelta(minutes=20),
    )
    InventoryMovement.objects.create(
        variant=locked_variant,
        reservation=reservation,
        kind=InventoryMovement.Kind.RESERVATION,
        quantity_delta=0,
        reference=reference,
    )
    return reservation


@transaction.atomic
def consume_reservation(reservation):
    locked = StockReservation.objects.select_for_update().select_related("variant").get(
        pk=reservation.pk
    )
    if locked.status == StockReservation.Status.CONSUMED:
        return locked
    if locked.status != StockReservation.Status.ACTIVE:
        return locked
    variant = ProductVariant.objects.select_for_update().get(pk=locked.variant_id)
    variant.on_hand -= locked.quantity
    variant.save(update_fields=["on_hand"])
    locked.status = StockReservation.Status.CONSUMED
    locked.consumed_at = timezone.now()
    locked.save(update_fields=["status", "consumed_at"])
    InventoryMovement.objects.create(
        variant=variant,
        reservation=locked,
        kind=InventoryMovement.Kind.SALE,
        quantity_delta=-locked.quantity,
        reference=locked.reference,
    )
    return locked


@transaction.atomic
def release_reservation(reservation):
    locked = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if locked.status != StockReservation.Status.ACTIVE:
        return locked
    locked.status = StockReservation.Status.RELEASED
    locked.released_at = timezone.now()
    locked.save(update_fields=["status", "released_at"])
    InventoryMovement.objects.create(
        variant=locked.variant,
        reservation=locked,
        kind=InventoryMovement.Kind.RELEASE,
        quantity_delta=0,
        reference=locked.reference,
    )
    return locked


@transaction.atomic
def create_pending_identity_order(
    *, cart, customer_snapshot, address_snapshot, fiscal_snapshot, fulfillment_method
):
    totals = calculate_cart_totals(cart)
    order = Order.objects.create(
        user=cart.user,
        customer_snapshot=customer_snapshot,
        address_snapshot=address_snapshot,
        fiscal_snapshot=fiscal_snapshot,
        coupon_code_snapshot=cart.coupon.code if cart.coupon_id else "",
        fulfillment_method=fulfillment_method,
        subtotal_snapshot=totals.subtotal,
        discount_snapshot=totals.discount,
        total_snapshot=totals.total,
    )
    for line in cart.lines.select_related("variant__product__category"):
        line_subtotal = money(line.variant.price * line.quantity)
        line_discount = best_automatic_discount(variant=line.variant, quantity=line.quantity)
        OrderItem.objects.create(
            order=order,
            variant=line.variant,
            product_name_snapshot=line.variant.product.name,
            variant_name_snapshot=line.variant.name,
            sku_snapshot=line.variant.sku,
            quantity=line.quantity,
            unit_price_snapshot=line.variant.price,
            discount_snapshot=line_discount,
            line_total_snapshot=money(line_subtotal - line_discount),
        )
    OrderAuditEvent.objects.create(order=order, kind="created_pending_identity")
    return order
