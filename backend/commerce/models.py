import uuid
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Category, Product, ProductVariant


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("This record is append-only")

    def delete(self):
        raise ValidationError("This record is append-only")


class AppendOnlyModel(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("This record is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("This record is append-only")


class DiscountType(models.TextChoices):
    FIXED = "fixed", "Fixed"
    PERCENTAGE = "percentage", "Percentage"


class ScheduledDiscount(models.Model):
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    enabled = models.BooleanField(default=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="%(class)s_schedule_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(value__gt=0)
                    & (
                        models.Q(discount_type="fixed")
                        | (
                            models.Q(discount_type="percentage")
                            & models.Q(value__lte=100)
                        )
                    )
                ),
                name="%(class)s_discount_valid",
            ),
        ]

    def clean(self):
        if self.starts_at >= self.ends_at:
            raise ValidationError("Discount start must precede its end")
        if self.value <= 0 or (self.discount_type == "percentage" and self.value > 100):
            raise ValidationError("Discount value is outside its valid range")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                condition=models.Q(user__isnull=False),
                name="unique_authenticated_user_cart",
            )
        ]

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
            models.UniqueConstraint(fields=("cart", "variant"), name="unique_cart_variant"),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="cart_quantity_positive"
            ),
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


class InventoryMovement(AppendOnlyModel):
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
    IMMUTABLE_FIELDS = (
        "user_id",
        "fulfillment_method",
        "customer_snapshot",
        "address_snapshot",
        "fiscal_snapshot",
        "coupon_code_snapshot",
        "subtotal_snapshot",
        "discount_snapshot",
        "total_snapshot",
    )
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

    def save(self, *args, **kwargs):
        if self.pk:
            original = (
                type(self)
                ._base_manager.filter(pk=self.pk)
                .values(*self.IMMUTABLE_FIELDS)
                .get()
            )
            if any(getattr(self, field) != original[field] for field in self.IMMUTABLE_FIELDS):
                raise ValidationError("Order snapshots are immutable")
            if not getattr(self, "_allow_status_transition", False):
                statuses = ("identity_status", "payment_status", "fulfillment_status")
                current = type(self)._base_manager.filter(pk=self.pk).values(*statuses).get()
                if any(getattr(self, field) != current[field] for field in statuses):
                    raise ValidationError("Order statuses require a transition service")
        return super().save(*args, **kwargs)


class OrderItem(AppendOnlyModel):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, on_delete=models.SET_NULL)
    product_name_snapshot = models.CharField(max_length=200)
    variant_name_snapshot = models.CharField(max_length=120, blank=True)
    sku_snapshot = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    discount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    line_total_snapshot = models.DecimalField(max_digits=12, decimal_places=2)


class OrderAuditEvent(AppendOnlyModel):
    order = models.ForeignKey(Order, related_name="audit_events", on_delete=models.CASCADE)
    kind = models.CharField(max_length=64)
    data = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
