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
                        | (models.Q(discount_type="percentage") & models.Q(value__lte=100))
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
    unit_price_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, editable=False
    )
    available_stock_snapshot = models.IntegerField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("cart", "variant"), name="unique_cart_variant"),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="cart_quantity_positive"
            ),
        ]


class StockReservationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use a reservation service")

    def delete(self):
        raise ValidationError("Stock reservations are immutable")


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
    objects = StockReservationQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_allow_lifecycle_transition", False):
            raise ValidationError("Use a reservation service")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock reservations are immutable")

    def _save_lifecycle_transition(self, *, update_fields):
        self._allow_lifecycle_transition = True
        try:
            self.save(update_fields=update_fields)
        finally:
            del self._allow_lifecycle_transition


class InventoryMovement(AppendOnlyModel):
    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Adjustment"
        RESERVATION = "reservation", "Reservation"
        SALE = "sale", "Sale"
        RELEASE = "release", "Release"
        REFUND = "refund", "Refund"

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
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="inventory_adjustments",
        on_delete=models.PROTECT,
    )
    source = models.CharField(max_length=32, default="domain")
    created_at = models.DateTimeField(auto_now_add=True)


class OrderQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use an order transition service")

    def delete(self):
        raise ValidationError("Orders are immutable")


class Order(models.Model):
    IMMUTABLE_FIELDS = (
        "checkout_idempotency_key",
        "user_id",
        "fulfillment_method",
        "customer_snapshot",
        "address_snapshot",
        "fiscal_snapshot",
        "coupon_code_snapshot",
        "subtotal_snapshot",
        "discount_snapshot",
        "shipping_amount_snapshot",
        "shipping_quote_id",
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
        NEEDS_ATTENTION = "needs_attention", "Needs attention"

    class FulfillmentStatus(models.TextChoices):
        UNFULFILLED = "unfulfilled", "Unfulfilled"
        PREPARING = "preparing", "Preparing"
        SHIPPED = "shipped", "Shipped"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    class FulfillmentMethod(models.TextChoices):
        SHIPPING = "shipping", "Shipping"
        PICKUP = "pickup", "Pickup"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_idempotency_key = models.UUIDField(null=True, blank=True, editable=False)
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
    shipping_amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_quote = models.ForeignKey(
        "ShippingQuote", null=True, blank=True, on_delete=models.PROTECT
    )
    reservations = models.ManyToManyField(StockReservation, related_name="orders", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = OrderQuerySet.as_manager()

    class Meta:
        permissions = (
            ("approve_identity_order", "Can manually approve order identity"),
            ("resume_order", "Can resume an approved order checkout"),
            ("cancel_order", "Can cancel an order through the guarded service"),
            ("refund_order", "Can refund an order through the guarded service"),
            ("create_shipment_order", "Can create an order shipment"),
            ("refresh_tracking_order", "Can refresh order tracking"),
            ("export_order", "Can export masked order data"),
            ("view_sensitive_order_data", "Can export unmasked order data"),
        )
        constraints = [
            models.UniqueConstraint(
                fields=("user", "checkout_idempotency_key"),
                condition=models.Q(checkout_idempotency_key__isnull=False),
                name="unique_user_checkout_idempotency_key",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = (
                type(self)._base_manager.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).get()
            )
            if any(getattr(self, field) != original[field] for field in self.IMMUTABLE_FIELDS):
                raise ValidationError("Order snapshots are immutable")
            if not getattr(self, "_allow_status_transition", False):
                statuses = ("identity_status", "payment_status", "fulfillment_status")
                current = type(self)._base_manager.filter(pk=self.pk).values(*statuses).get()
                if any(getattr(self, field) != current[field] for field in statuses):
                    raise ValidationError("Order statuses require a transition service")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Orders are immutable")

    def _save_status_transition(self, *, field):
        self._allow_status_transition = True
        try:
            self.save(update_fields=[field])
        finally:
            del self._allow_status_transition


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


class IdentityVerification(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="identity_verifications", on_delete=models.PROTECT
    )
    order = models.ForeignKey(
        Order,
        related_name="identity_verifications",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    consent_version = models.CharField(max_length=64)
    consented_at = models.DateTimeField()
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=24, choices=Status.choices)
    provider_reference = models.CharField(max_length=160, blank=True)
    masked_audit = models.JSONField(default=dict)
    staff_diagnostics = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="identity_reviews",
        on_delete=models.PROTECT,
    )
    review_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PackageBox(models.Model):
    code = models.CharField(max_length=64, unique=True)
    inner_length_cm = models.DecimalField(max_digits=9, decimal_places=2)
    inner_width_cm = models.DecimalField(max_digits=9, decimal_places=2)
    inner_height_cm = models.DecimalField(max_digits=9, decimal_places=2)
    tare_weight_grams = models.PositiveIntegerField()
    max_weight_grams = models.PositiveIntegerField()
    enabled = models.BooleanField(default=True)


class ShippingQuote(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="shipping_quotes", on_delete=models.CASCADE
    )
    provider = models.CharField(max_length=32, default="correo_argentino")
    service = models.CharField(max_length=64)
    postal_code = models.CharField(max_length=8)
    parcels = models.JSONField(default=list)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    surcharge_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="ARS")
    cart_fingerprint = models.CharField(max_length=64)
    provider_summary = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NEEDS_ATTENTION = "needs_attention", "Needs attention"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(Order, related_name="payment_transactions", on_delete=models.PROTECT)
    provider = models.CharField(max_length=32, default="mercadopago")
    external_reference = models.UUIDField(unique=True, default=uuid.uuid4)
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4)
    preference_id = models.CharField(max_length=160, unique=True, null=True, blank=True)
    payment_id = models.CharField(max_length=160, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="ARS")
    expected_collector_id = models.CharField(max_length=160, blank=True)
    live_mode = models.BooleanField(default=False)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    provider_status = models.CharField(max_length=64, blank=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    provider_summary = models.JSONField(default=dict)
    staff_diagnostics = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PaymentWebhookEvent(models.Model):
    provider = models.CharField(max_length=32, default="mercadopago")
    event_id = models.CharField(max_length=160)
    request_id = models.CharField(max_length=160, blank=True)
    payment_id = models.CharField(max_length=160, blank=True)
    raw_body_hash = models.CharField(max_length=64)
    signature_valid = models.BooleanField(default=False)
    status = models.CharField(max_length=24, default="received")
    staff_diagnostics = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "event_id"), name="unique_payment_provider_event"
            )
        ]


class Shipment(models.Model):
    order = models.OneToOneField(Order, related_name="shipment", on_delete=models.PROTECT)
    provider = models.CharField(max_length=32, default="correo_argentino")
    provider_id = models.CharField(max_length=160, unique=True)
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4)
    tracking_number = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=64, default="created")
    label_url = models.URLField(max_length=500, blank=True)
    provider_summary = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ShipmentParcelImport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IMPORTED = "imported", "Imported"

    shipment = models.ForeignKey(
        Shipment,
        related_name="parcel_imports",
        on_delete=models.PROTECT,
    )
    parcel_index = models.PositiveIntegerField()
    external_id = models.CharField(max_length=160, unique=True)
    idempotency_key = models.UUIDField(unique=True)
    parcel_snapshot = models.JSONField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    provider_summary = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("parcel_index",)
        constraints = [
            models.UniqueConstraint(
                fields=("shipment", "parcel_index"),
                name="unique_shipment_parcel_import_index",
            )
        ]


class Refund(models.Model):
    order = models.ForeignKey(Order, related_name="refunds", on_delete=models.PROTECT)
    transaction = models.ForeignKey(
        PaymentTransaction, related_name="refunds", on_delete=models.PROTECT
    )
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4)
    provider_refund_id = models.CharField(max_length=160, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32, default="pending")
    stock_restored = models.BooleanField(default=False)
    return_required = models.BooleanField(default=False)
    staff_diagnostics = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationAttempt(models.Model):
    kind = models.CharField(max_length=64)
    reference = models.CharField(max_length=160)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ExternalProviderFailure(models.Model):
    correlation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    operation = models.CharField(max_length=80)
    code = models.CharField(max_length=32)
    staff_diagnostics = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffExportAudit(AppendOnlyModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="staff_exports", on_delete=models.PROTECT
    )
    resource = models.CharField(max_length=64)
    export_format = models.CharField(max_length=8)
    filters = models.JSONField(default=dict)
    row_count = models.PositiveIntegerField()
    included_sensitive_data = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
