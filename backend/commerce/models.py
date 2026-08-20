import uuid

from django.conf import settings
from django.core import signing
from django.db import models
from django.utils import timezone

from catalog.models import Category, Product, ProductVariant


class DiscountType(models.TextChoices):
    FIXED = "fixed", "Fixed"
    PERCENTAGE = "percentage", "Percentage"


class ScheduledDiscount(models.Model):
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    enabled = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def is_active(self, at=None):
        checked_at = at or timezone.now()
        return self.enabled and self.starts_at <= checked_at <= self.ends_at


class PromotionRule(ScheduledDiscount):
    name = models.CharField(max_length=160)
    products = models.ManyToManyField(Product, related_name="promotion_rules", blank=True)
    categories = models.ManyToManyField(Category, related_name="promotion_rules", blank=True)


class Coupon(ScheduledDiscount):
    code = models.CharField(max_length=64, unique=True)
    combinable = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        return super().save(*args, **kwargs)


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="carts",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    anonymous_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def signed_token(self):
        return signing.dumps(str(self.anonymous_token), salt="commerce.cart")

    @classmethod
    def from_signed_token(cls, token):
        value = signing.loads(token, salt="commerce.cart")
        return cls.objects.get(anonymous_token=value, user__isnull=True)


class CartLine(models.Model):
    cart = models.ForeignKey(Cart, related_name="lines", on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, related_name="cart_lines", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("cart", "variant"), name="unique_cart_variant")
        ]


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONSUMED = "consumed", "Consumed"
        RELEASED = "released", "Released"

    variant = models.ForeignKey(
        ProductVariant, related_name="stock_reservations", on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField()
    reference = models.CharField(max_length=160)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)


class InventoryMovement(models.Model):
    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Adjustment"
        RESERVATION = "reservation", "Reservation"
        SALE = "sale", "Sale"
        RELEASE = "release", "Release"

    variant = models.ForeignKey(
        ProductVariant, related_name="inventory_movements", on_delete=models.PROTECT
    )
    reservation = models.ForeignKey(
        StockReservation,
        related_name="movements",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    quantity_delta = models.IntegerField()
    reference = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    class IdentityStatus(models.TextChoices):
        PENDING = "pending_identity", "Pending identity"
        VERIFIED = "verified", "Verified"
        MANUAL_REVIEW = "manual_review", "Manual review"

    class PaymentStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class FulfillmentStatus(models.TextChoices):
        UNFULFILLED = "unfulfilled", "Unfulfilled"
        PREPARING = "preparing", "Preparing"
        SHIPPED = "shipped", "Shipped"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        FULFILLED = "fulfilled", "Fulfilled"

    class FulfillmentMethod(models.TextChoices):
        SHIPPING = "shipping", "Shipping"
        PICKUP = "pickup", "Pickup"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.PROTECT
    )
    identity_status = models.CharField(
        max_length=24, choices=IdentityStatus.choices, default=IdentityStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=24, choices=PaymentStatus.choices, default=PaymentStatus.NOT_STARTED
    )
    fulfillment_status = models.CharField(
        max_length=24, choices=FulfillmentStatus.choices, default=FulfillmentStatus.UNFULFILLED
    )
    fulfillment_method = models.CharField(max_length=16, choices=FulfillmentMethod.choices)
    customer_snapshot = models.JSONField()
    address_snapshot = models.JSONField()
    fiscal_snapshot = models.JSONField()
    coupon_code_snapshot = models.CharField(max_length=64, blank=True)
    subtotal_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    discount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    total_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    reservations = models.ManyToManyField(StockReservation, related_name="orders", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, on_delete=models.SET_NULL)
    product_name_snapshot = models.CharField(max_length=200)
    variant_name_snapshot = models.CharField(max_length=120, blank=True)
    sku_snapshot = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    discount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    line_total_snapshot = models.DecimalField(max_digits=12, decimal_places=2)


class OrderAuditEvent(models.Model):
    order = models.ForeignKey(Order, related_name="audit_events", on_delete=models.CASCADE)
    kind = models.CharField(max_length=64)
    data = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
