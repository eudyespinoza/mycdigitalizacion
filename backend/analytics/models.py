import uuid

from django.db import models
from django.utils import timezone


class AnalyticsSession(models.Model):
    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        UNKNOWN = "unknown", "Unknown"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    visitor_hash = models.CharField(max_length=64, db_index=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=80, blank=True)
    campaign = models.CharField(max_length=120, blank=True)
    referrer_domain = models.CharField(max_length=255, blank=True)
    device = models.CharField(
        max_length=16,
        choices=Device.choices,
        default=Device.UNKNOWN,
    )
    entry_path = models.CharField(max_length=255)
    viewed_product = models.BooleanField(default=False)
    added_to_cart = models.BooleanField(default=False)
    started_checkout = models.BooleanField(default=False)
    selected_delivery = models.BooleanField(default=False)
    started_payment = models.BooleanField(default=False)
    first_converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = (
            ("view_web_analytics", "Can view web analytics"),
            ("view_commercial_analytics", "Can view commercial analytics"),
            ("export_commercial_analytics", "Can export commercial analytics"),
        )
        indexes = [
            models.Index(fields=("started_at", "source"), name="an_session_source_idx"),
            models.Index(fields=("started_at", "device"), name="an_session_device_idx"),
            models.Index(
                fields=("first_converted_at", "started_at"),
                name="an_session_conversion_idx",
            ),
        ]


class AnalyticsEvent(models.Model):
    class EventType(models.TextChoices):
        PAGE_VIEW = "page_view", "Page view"
        PRODUCT_VIEW = "product_view", "Product view"
        ADD_TO_CART = "add_to_cart", "Add to cart"
        CHECKOUT_STARTED = "checkout_started", "Checkout started"
        DELIVERY_SELECTED = "delivery_selected", "Delivery selected"
        PAYMENT_STARTED = "payment_started", "Payment started"

    event_id = models.UUIDField(unique=True, editable=False)
    session = models.ForeignKey(
        AnalyticsSession,
        related_name="events",
        on_delete=models.CASCADE,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    product = models.ForeignKey(
        "catalog.Product",
        related_name="analytics_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        related_name="analytics_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    order = models.ForeignKey(
        "commerce.Order",
        related_name="analytics_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    path = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    dimensions = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=("event_type", "occurred_at"),
                name="an_event_type_time_idx",
            ),
            models.Index(
                fields=("session", "occurred_at"),
                name="an_event_session_idx",
            ),
            models.Index(
                fields=("product", "occurred_at"),
                name="an_event_product_idx",
            ),
        ]


class AnalyticsOrderAttribution(models.Model):
    order = models.OneToOneField(
        "commerce.Order",
        related_name="analytics_attribution",
        on_delete=models.CASCADE,
    )
    session = models.ForeignKey(
        AnalyticsSession,
        related_name="attributed_orders",
        null=True,
        on_delete=models.SET_NULL,
    )
    attributed_at = models.DateTimeField(default=timezone.now)


class AnalyticsConversion(models.Model):
    session = models.ForeignKey(
        AnalyticsSession,
        related_name="conversions",
        null=True,
        on_delete=models.SET_NULL,
    )
    order = models.OneToOneField(
        "commerce.Order",
        related_name="analytics_conversion",
        on_delete=models.PROTECT,
    )
    transaction = models.OneToOneField(
        "commerce.PaymentTransaction",
        related_name="analytics_conversion",
        on_delete=models.PROTECT,
    )
    approved_at = models.DateTimeField(db_index=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class AnalyticsDailyProduct(models.Model):
    day = models.DateField()
    product = models.ForeignKey(
        "catalog.Product",
        related_name="daily_analytics",
        on_delete=models.CASCADE,
    )
    views = models.PositiveIntegerField(default=0)
    viewing_sessions = models.PositiveIntegerField(default=0)
    cart_additions = models.PositiveIntegerField(default=0)
    attributed_checkouts = models.PositiveIntegerField(default=0)
    paid_orders = models.PositiveIntegerField(default=0)
    units = models.PositiveIntegerField(default=0)
    product_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discounts = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("day", "product"),
                name="an_daily_product_unique",
            )
        ]
        indexes = [models.Index(fields=("day", "product"), name="an_daily_product_idx")]


class AnalyticsDailyChannel(models.Model):
    day = models.DateField()
    source = models.CharField(max_length=80, blank=True)
    medium = models.CharField(max_length=80, blank=True)
    campaign = models.CharField(max_length=120, blank=True)
    device = models.CharField(
        max_length=16,
        choices=AnalyticsSession.Device.choices,
        default=AnalyticsSession.Device.UNKNOWN,
    )
    sessions = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    product_views = models.PositiveIntegerField(default=0)
    cart_additions = models.PositiveIntegerField(default=0)
    checkout_starts = models.PositiveIntegerField(default=0)
    delivery_selections = models.PositiveIntegerField(default=0)
    payment_starts = models.PositiveIntegerField(default=0)
    paid_orders = models.PositiveIntegerField(default=0)
    attributed_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("day", "source", "medium", "campaign", "device"),
                name="an_daily_channel_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=("day", "source", "medium", "device"),
                name="an_daily_channel_idx",
            )
        ]
