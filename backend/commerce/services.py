from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
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
    if value <= 0 or (discount_type == "percentage" and value > 100):
        raise ValidationError("Discount value is outside its valid range")
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
        discount_amount(rule.discount_type, rule.value, line_amount) for rule in rules.distinct()
    ]
    return max(discounts, default=Decimal("0.00"))


@dataclass(frozen=True)
class CartTotals:
    subtotal: Decimal
    discount: Decimal
    total: Decimal


@dataclass(frozen=True)
class PricedLine:
    cart_line: CartLine
    subtotal: Decimal
    discount: Decimal
    total: Decimal


def _allocate_discount(total, capacities):
    total = money(total)
    capacity_total = sum(capacities, Decimal("0"))
    if total <= 0 or capacity_total <= 0:
        return [Decimal("0.00") for _ in capacities]
    allocations = [
        min(capacity, (total * capacity / capacity_total).quantize(MONEY, rounding=ROUND_DOWN))
        for capacity in capacities
    ]
    remainder = money(total - sum(allocations, Decimal("0")))
    while remainder >= MONEY:
        changed = False
        for index, capacity in enumerate(capacities):
            if allocations[index] + MONEY <= capacity:
                allocations[index] += MONEY
                remainder -= MONEY
                changed = True
                if remainder < MONEY:
                    break
        if not changed:
            break
    return [money(value) for value in allocations]


def price_cart_lines(lines, *, coupon=None, at=None):
    checked_at = at or timezone.now()
    ordered_lines = sorted(lines, key=lambda line: line.pk)
    subtotals = [money(line.variant.price * line.quantity) for line in ordered_lines]
    automatic = [
        best_automatic_discount(variant=line.variant, quantity=line.quantity, at=checked_at)
        for line in ordered_lines
    ]
    subtotal = money(sum(subtotals, Decimal("0")))
    automatic_total = money(sum(automatic, Decimal("0")))
    base_discounts = automatic
    coupon_to_allocate = Decimal("0.00")
    if coupon and coupon.is_active(checked_at):
        coupon_discount = discount_amount(coupon.discount_type, coupon.value, subtotal)
        if coupon.combinable:
            coupon_to_allocate = min(coupon_discount, money(subtotal - automatic_total))
        elif coupon_discount > automatic_total:
            base_discounts = [Decimal("0.00") for _ in ordered_lines]
            coupon_to_allocate = coupon_discount
    capacities = [
        money(value - discount) for value, discount in zip(subtotals, base_discounts, strict=False)
    ]
    coupon_allocations = _allocate_discount(coupon_to_allocate, capacities)
    priced = []
    for line, line_subtotal, base, coupon_part in zip(
        ordered_lines, subtotals, base_discounts, coupon_allocations, strict=False
    ):
        line_discount = min(line_subtotal, money(base + coupon_part))
        priced.append(
            PricedLine(
                cart_line=line,
                subtotal=line_subtotal,
                discount=line_discount,
                total=money(line_subtotal - line_discount),
            )
        )
    return priced


def calculate_cart_totals(cart, *, at=None):
    checked_at = at or timezone.now()
    lines = list(cart.lines.select_related("variant__product__category"))
    if any(
        not line.variant.is_active
        or not line.variant.product.is_active
        or not line.variant.product.is_sellable
        for line in lines
    ):
        raise ValidationError("Cart contains an unavailable variant")
    priced = price_cart_lines(lines, coupon=cart.coupon, at=checked_at)
    subtotal = money(sum((line.subtotal for line in priced), Decimal("0")))
    discount = money(sum((line.discount for line in priced), Decimal("0")))
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


def get_or_create_user_cart(*, user):
    existing = Cart.objects.filter(user=user).first()
    if existing:
        return existing
    try:
        with transaction.atomic():
            return Cart.objects.create(user=user)
    except IntegrityError:
        return Cart.objects.get(user=user)


@transaction.atomic
def add_cart_line(*, cart, variant, quantity):
    if quantity < 1:
        raise ValidationError("Quantity must be positive")
    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
    available_variant = ProductVariant.objects.filter(
        pk=variant.pk,
        is_active=True,
        product__is_active=True,
        product__is_sellable=True,
    ).first()
    if not available_variant:
        raise ValidationError("Variant is unavailable")
    updated = CartLine.objects.filter(cart=locked_cart, variant=available_variant).update(
        quantity=F("quantity") + quantity
    )
    if not updated:
        CartLine.objects.create(cart=locked_cart, variant=available_variant, quantity=quantity)
    return locked_cart.lines.get(variant=available_variant)


def merge_carts(*, anonymous_cart, user):
    destination = get_or_create_user_cart(user=user)
    with transaction.atomic():
        locked = {
            cart.pk: cart
            for cart in Cart.objects.select_for_update()
            .filter(pk__in=(anonymous_cart.pk, destination.pk))
            .order_by("pk")
        }
        source = locked.get(anonymous_cart.pk)
        target = locked[destination.pk]
        if not source:
            return target
        for source_line in source.lines.order_by("pk"):
            updated = CartLine.objects.filter(
                cart=target, variant_id=source_line.variant_id
            ).update(quantity=F("quantity") + source_line.quantity)
            if not updated:
                CartLine.objects.create(
                    cart=target,
                    variant_id=source_line.variant_id,
                    quantity=source_line.quantity,
                )
        if not target.coupon_id and source.coupon_id:
            target.coupon_id = source.coupon_id
            target.save(update_fields=["coupon"])
        source.delete()
        return target


class InsufficientStock(ValidationError):
    pass


@transaction.atomic
def create_reservation(*, variant, quantity, reference, expires_at=None):
    if quantity < 1:
        raise ValidationError("Reservation quantity must be positive")
    locked_variant = ProductVariant.objects.select_for_update().get(pk=variant.pk)
    now = timezone.now()
    effective_expiry = expires_at or now + timezone.timedelta(minutes=20)
    if effective_expiry <= now:
        raise ValidationError("Reservation expiry must be in the future")
    expired = list(
        StockReservation.objects.select_for_update().filter(
            variant=locked_variant,
            status=StockReservation.Status.ACTIVE,
            expires_at__lte=now,
        )
    )
    for reservation in expired:
        reservation.status = StockReservation.Status.RELEASED
        reservation.released_at = now
        reservation._save_lifecycle_transition(update_fields=["status", "released_at"])
        InventoryMovement.objects.create(
            variant=locked_variant,
            reservation=reservation,
            kind=InventoryMovement.Kind.RELEASE,
            quantity_delta=0,
            reference=reservation.reference,
        )
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
        expires_at=effective_expiry,
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
    variant_id = StockReservation.objects.values_list("variant_id", flat=True).get(
        pk=reservation.pk
    )
    variant = ProductVariant.objects.select_for_update().get(pk=variant_id)
    locked = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if locked.status == StockReservation.Status.CONSUMED:
        return locked
    if locked.status != StockReservation.Status.ACTIVE:
        return locked
    if locked.expires_at <= timezone.now():
        locked.status = StockReservation.Status.RELEASED
        locked.released_at = timezone.now()
        locked._save_lifecycle_transition(update_fields=["status", "released_at"])
        InventoryMovement.objects.create(
            variant=variant,
            reservation=locked,
            kind=InventoryMovement.Kind.RELEASE,
            quantity_delta=0,
            reference=locked.reference,
        )
        return locked
    variant.on_hand -= locked.quantity
    variant.save(update_fields=["on_hand"])
    locked.status = StockReservation.Status.CONSUMED
    locked.consumed_at = timezone.now()
    locked._save_lifecycle_transition(update_fields=["status", "consumed_at"])
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
    variant_id = StockReservation.objects.values_list("variant_id", flat=True).get(
        pk=reservation.pk
    )
    variant = ProductVariant.objects.select_for_update().get(pk=variant_id)
    locked = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if locked.status != StockReservation.Status.ACTIVE:
        return locked
    locked.status = StockReservation.Status.RELEASED
    locked.released_at = timezone.now()
    locked._save_lifecycle_transition(update_fields=["status", "released_at"])
    InventoryMovement.objects.create(
        variant=variant,
        reservation=locked,
        kind=InventoryMovement.Kind.RELEASE,
        quantity_delta=0,
        reference=locked.reference,
    )
    return locked


@transaction.atomic
def create_pending_identity_order(
    *,
    cart,
    customer_snapshot,
    address_snapshot,
    fiscal_snapshot,
    fulfillment_method,
    shipping_quote=None,
    at=None,
):
    checked_at = at or timezone.now()
    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if locked_cart.coupon_id:
        locked_cart.coupon = Coupon.objects.select_for_update().get(pk=locked_cart.coupon_id)
    line_refs = list(
        CartLine.objects.select_for_update()
        .filter(cart=locked_cart)
        .order_by("pk")
        .values("pk", "variant_id")
    )
    list(
        ProductVariant.objects.select_for_update().filter(
            pk__in=[line["variant_id"] for line in line_refs]
        )
    )
    lines = list(
        CartLine.objects.filter(pk__in=[line["pk"] for line in line_refs]).select_related(
            "variant__product__category"
        )
    )
    if any(
        not line.variant.is_active
        or not line.variant.product.is_active
        or not line.variant.product.is_sellable
        for line in lines
    ):
        raise ValidationError("Cart contains an unavailable variant")
    priced_lines = price_cart_lines(lines, coupon=locked_cart.coupon, at=checked_at)
    subtotal = money(sum((line.subtotal for line in priced_lines), Decimal("0")))
    discount = money(sum((line.discount for line in priced_lines), Decimal("0")))
    merchandise_total = money(sum((line.total for line in priced_lines), Decimal("0")))
    shipping_amount = money(shipping_quote.total_amount if shipping_quote else 0)
    total = money(merchandise_total + shipping_amount)
    order = Order.objects.create(
        user=locked_cart.user,
        customer_snapshot=customer_snapshot,
        address_snapshot=address_snapshot,
        fiscal_snapshot=fiscal_snapshot,
        coupon_code_snapshot=locked_cart.coupon.code if locked_cart.coupon_id else "",
        fulfillment_method=fulfillment_method,
        shipping_quote=shipping_quote,
        subtotal_snapshot=subtotal,
        discount_snapshot=discount,
        shipping_amount_snapshot=shipping_amount,
        total_snapshot=total,
    )
    for priced in priced_lines:
        line = priced.cart_line
        OrderItem.objects.create(
            order=order,
            variant=line.variant,
            product_name_snapshot=line.variant.product.name,
            variant_name_snapshot=line.variant.name,
            sku_snapshot=line.variant.sku,
            quantity=line.quantity,
            unit_price_snapshot=line.variant.price,
            discount_snapshot=priced.discount,
            line_total_snapshot=priced.total,
        )
    if (
        sum((item.line_total_snapshot for item in order.items.all()), Decimal("0"))
        + shipping_amount
        != total
    ):
        raise ValidationError("Order item snapshots do not reconcile with order total")
    OrderAuditEvent.objects.create(order=order, kind="created_pending_identity")
    return order


@transaction.atomic
def transition_order_status(*, order, field, value, actor=None):
    allowed = {
        "identity_status": dict(Order.IdentityStatus.choices),
        "payment_status": dict(Order.PaymentStatus.choices),
        "fulfillment_status": dict(Order.FulfillmentStatus.choices),
    }
    if field not in allowed or value not in allowed[field]:
        raise ValidationError("Invalid order status transition")
    locked = Order.objects.select_for_update().get(pk=order.pk)
    previous = getattr(locked, field)
    if previous == value:
        return locked
    setattr(locked, field, value)
    locked._save_status_transition(field=field)
    OrderAuditEvent.objects.create(
        order=locked,
        kind=f"{field}_changed",
        data={"from": previous, "to": value},
        actor=actor,
    )
    return locked
