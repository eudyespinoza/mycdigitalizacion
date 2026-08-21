import uuid
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from catalog.models import ProductVariant
from commerce.models import (
    Cart,
    CartLine,
    Coupon,
    CouponRedemption,
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
    product = variant.product
    product_rules = getattr(product, "active_catalog_promotions", None)
    category_rules = getattr(product.category, "active_catalog_promotions", None)
    if product_rules is not None and category_rules is not None:
        rules = {rule.pk: rule for rule in (*product_rules, *category_rules)}.values()
    else:
        rules = (
            PromotionRule.objects.filter(
                enabled=True,
                starts_at__lte=checked_at,
                ends_at__gte=checked_at,
            )
            .filter(Q(products=product) | Q(categories=product.category))
            .distinct()
        )
    discounts = [
        discount_amount(rule.discount_type, rule.value, line_amount) for rule in rules
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


def _release_expired_coupon_redemptions(*, coupon, at):
    return CouponRedemption.objects.select_for_update().filter(
        coupon=coupon,
        status=CouponRedemption.Status.RESERVED,
        expires_at__lte=at,
    ).update(
        status=CouponRedemption.Status.RELEASED,
        released_at=at,
    )


def _coupon_redemptions_in_use(*, coupon, at, exclude=None):
    queryset = CouponRedemption.objects.filter(coupon=coupon).filter(
        Q(status=CouponRedemption.Status.CONSUMED)
        | Q(status=CouponRedemption.Status.RESERVED, expires_at__gt=at)
    )
    if exclude is not None:
        queryset = queryset.exclude(pk=exclude)
    return queryset.count()


def _ensure_coupon_capacity(*, coupon, at, exclude=None):
    _release_expired_coupon_redemptions(coupon=coupon, at=at)
    if coupon.max_redemptions is None:
        return
    if _coupon_redemptions_in_use(coupon=coupon, at=at, exclude=exclude) >= coupon.max_redemptions:
        raise ValidationError("El cupo de usos de este cupón está agotado.")


@transaction.atomic
def reserve_coupon_redemption(*, coupon, order, expires_at=None, at=None):
    checked_at = at or timezone.now()
    effective_expiry = expires_at or checked_at + timezone.timedelta(minutes=20)
    locked_coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
    redemption = CouponRedemption.objects.select_for_update().filter(order=order).first()
    if redemption and redemption.coupon_id != locked_coupon.pk:
        raise ValidationError("El pedido ya tiene otro cupón reservado.")
    if (
        redemption
        and redemption.status == CouponRedemption.Status.RESERVED
        and redemption.expires_at > checked_at
    ):
        return redemption
    if redemption and redemption.status == CouponRedemption.Status.CONSUMED:
        return redemption
    _ensure_coupon_capacity(
        coupon=locked_coupon,
        at=checked_at,
        exclude=redemption.pk if redemption else None,
    )
    if redemption:
        redemption.status = CouponRedemption.Status.RESERVED
        redemption.reserved_at = checked_at
        redemption.expires_at = effective_expiry
        redemption.consumed_at = None
        redemption.released_at = None
        redemption.save(
            update_fields=(
                "status",
                "reserved_at",
                "expires_at",
                "consumed_at",
                "released_at",
            )
        )
        return redemption
    return CouponRedemption.objects.create(
        coupon=locked_coupon,
        order=order,
        expires_at=effective_expiry,
        reserved_at=checked_at,
    )


@transaction.atomic
def consume_coupon_redemption(*, order, at=None):
    checked_at = at or timezone.now()
    redemption = (
        CouponRedemption.objects.select_for_update()
        .select_related("coupon")
        .filter(order=order)
        .first()
    )
    if not redemption or redemption.status == CouponRedemption.Status.CONSUMED:
        return redemption
    coupon = Coupon.objects.select_for_update().get(pk=redemption.coupon_id)
    _ensure_coupon_capacity(
        coupon=coupon,
        at=checked_at,
        exclude=redemption.pk,
    )
    redemption.status = CouponRedemption.Status.CONSUMED
    redemption.consumed_at = checked_at
    redemption.released_at = None
    redemption.save(update_fields=("status", "consumed_at", "released_at"))
    return redemption


@transaction.atomic
def release_coupon_redemption(*, order, at=None):
    redemption = CouponRedemption.objects.select_for_update().filter(order=order).first()
    if not redemption or redemption.status == CouponRedemption.Status.RELEASED:
        return redemption
    redemption.status = CouponRedemption.Status.RELEASED
    redemption.released_at = at or timezone.now()
    redemption.save(update_fields=("status", "released_at"))
    return redemption


def release_expired_coupon_redemptions(*, at=None):
    checked_at = at or timezone.now()
    return CouponRedemption.objects.filter(
        status=CouponRedemption.Status.RESERVED,
        expires_at__lte=checked_at,
    ).update(
        status=CouponRedemption.Status.RELEASED,
        released_at=checked_at,
    )


@transaction.atomic
def apply_coupon(cart, code, *, at=None):
    if cart.coupon_id:
        raise ValidationError("A cart accepts only one coupon")
    checked_at = at or timezone.now()
    try:
        coupon = Coupon.objects.select_for_update().get(code=code.strip().upper())
    except Coupon.DoesNotExist as exc:
        raise ValidationError("Coupon is invalid") from exc
    if not coupon.is_active(checked_at):
        raise ValidationError("Coupon is not active")
    _ensure_coupon_capacity(coupon=coupon, at=checked_at)
    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
    locked_cart.coupon = coupon
    locked_cart.save(update_fields=["coupon", "updated_at"])
    cart.coupon = coupon
    cart.updated_at = locked_cart.updated_at
    return locked_cart


def get_or_create_user_cart(*, user):
    existing = Cart.objects.filter(user=user).first()
    if existing:
        return existing
    try:
        with transaction.atomic():
            return Cart.objects.create(user=user)
    except IntegrityError:
        return Cart.objects.get(user=user)


class PurchaseLimitExceeded(ValidationError):
    pass


def purchase_quantity_limit(variant):
    limits = []
    if not variant.stock_is_infinite:
        annotated = getattr(variant, "available_stock_value", None)
        available = variant.available_stock if annotated is None else annotated
        limits.append(max(available, 0))
    if variant.max_purchase_quantity is not None:
        limits.append(variant.max_purchase_quantity)
    return min(limits) if limits else None


def validate_purchase_quantity(*, variant, quantity):
    if quantity < 1:
        raise ValidationError("Quantity must be positive")
    if quantity > settings.MAX_CART_LINE_QUANTITY:
        raise PurchaseLimitExceeded(
            "La cantidad solicitada supera el límite seguro por variante."
        )
    limit = purchase_quantity_limit(variant)
    if limit is not None and quantity > limit:
        raise PurchaseLimitExceeded(
            f"La cantidad máxima disponible para esta variante es {limit}."
        )
    return limit


@transaction.atomic
def add_cart_line(*, cart, variant, quantity):
    if quantity < 1:
        raise ValidationError("Quantity must be positive")
    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
    available_variant = ProductVariant.objects.select_for_update().filter(
        pk=variant.pk,
        is_active=True,
        product__is_active=True,
        product__is_sellable=True,
    ).first()
    if not available_variant:
        raise ValidationError("Variant is unavailable")
    line = CartLine.objects.select_for_update().filter(
        cart=locked_cart,
        variant=available_variant,
    ).first()
    requested_quantity = quantity + (line.quantity if line else 0)
    limit = validate_purchase_quantity(
        variant=available_variant,
        quantity=requested_quantity,
    )
    if line:
        line.quantity = requested_quantity
        line.available_stock_snapshot = limit
        line.save(update_fields=("quantity", "available_stock_snapshot"))
    else:
        line = CartLine.objects.create(
            cart=locked_cart,
            variant=available_variant,
            quantity=quantity,
            unit_price_snapshot=available_variant.price,
            available_stock_snapshot=limit,
        )
    return line


@transaction.atomic
def set_cart_line_quantity(*, cart, variant_id, quantity):
    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
    line = (
        CartLine.objects.select_for_update()
        .select_related("variant")
        .filter(cart=locked_cart, variant_id=variant_id)
        .first()
    )
    if not line:
        raise CartLine.DoesNotExist
    if quantity < 1:
        line.delete()
        return None
    limit = validate_purchase_quantity(variant=line.variant, quantity=quantity)
    line.quantity = quantity
    line.available_stock_snapshot = limit
    line.save(update_fields=("quantity", "available_stock_snapshot"))
    return line


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
            variant = ProductVariant.objects.select_for_update().get(
                pk=source_line.variant_id
            )
            target_line = CartLine.objects.select_for_update().filter(
                cart=target,
                variant_id=source_line.variant_id,
            ).first()
            combined_quantity = source_line.quantity + (
                target_line.quantity if target_line else 0
            )
            limit = purchase_quantity_limit(variant)
            accepted_quantity = min(
                combined_quantity,
                settings.MAX_CART_LINE_QUANTITY,
            )
            if limit is not None:
                accepted_quantity = min(accepted_quantity, limit)
            if target_line and accepted_quantity > 0:
                target_line.quantity = accepted_quantity
                target_line.available_stock_snapshot = limit
                target_line.save(update_fields=("quantity", "available_stock_snapshot"))
            elif target_line:
                target_line.delete()
            elif accepted_quantity > 0:
                CartLine.objects.create(
                    cart=target,
                    variant_id=source_line.variant_id,
                    quantity=accepted_quantity,
                    unit_price_snapshot=source_line.unit_price_snapshot,
                    available_stock_snapshot=limit,
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
    if quantity > settings.MAX_CART_LINE_QUANTITY:
        raise PurchaseLimitExceeded(
            "La cantidad solicitada supera el límite seguro por variante."
        )
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
        if reservation.tracks_inventory:
            InventoryMovement.objects.create(
                variant=locked_variant,
                reservation=reservation,
                kind=InventoryMovement.Kind.RELEASE,
                quantity_delta=0,
                reference=reservation.reference,
            )
    if (
        locked_variant.max_purchase_quantity is not None
        and quantity > locked_variant.max_purchase_quantity
    ):
        raise PurchaseLimitExceeded(
            f"La cantidad máxima permitida por compra es "
            f"{locked_variant.max_purchase_quantity}."
        )
    reserved = (
        StockReservation.objects.filter(
            variant=locked_variant,
            status=StockReservation.Status.ACTIVE,
            tracks_inventory=True,
            expires_at__gt=now,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    if not locked_variant.stock_is_infinite and locked_variant.on_hand - reserved < quantity:
        raise InsufficientStock("Insufficient available stock")
    reservation = StockReservation.objects.create(
        variant=locked_variant,
        quantity=quantity,
        reference=reference,
        expires_at=effective_expiry,
        tracks_inventory=not locked_variant.stock_is_infinite,
    )
    if reservation.tracks_inventory:
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
        if locked.tracks_inventory:
            InventoryMovement.objects.create(
                variant=variant,
                reservation=locked,
                kind=InventoryMovement.Kind.RELEASE,
                quantity_delta=0,
                reference=locked.reference,
            )
        return locked
    if locked.tracks_inventory:
        variant.on_hand -= locked.quantity
        variant.save(update_fields=["on_hand"])
    locked.status = StockReservation.Status.CONSUMED
    locked.consumed_at = timezone.now()
    locked._save_lifecycle_transition(update_fields=["status", "consumed_at"])
    if locked.tracks_inventory:
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
    if locked.tracks_inventory:
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
    checkout_idempotency_key=None,
    public_id=None,
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
        public_id=public_id or uuid.uuid4(),
        user=locked_cart.user,
        checkout_idempotency_key=checkout_idempotency_key,
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
    if locked_cart.coupon_id:
        reserve_coupon_redemption(
            coupon=locked_cart.coupon,
            order=order,
            expires_at=checked_at + timezone.timedelta(minutes=20),
            at=checked_at,
        )
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
