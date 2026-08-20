from django.contrib import admin

from commerce.models import (
    Cart,
    CartLine,
    Coupon,
    ExternalProviderFailure,
    IdentityVerification,
    InventoryMovement,
    NotificationAttempt,
    Order,
    OrderAuditEvent,
    OrderItem,
    PackageBox,
    PaymentTransaction,
    PaymentWebhookEvent,
    PromotionRule,
    Refund,
    Shipment,
    ShippingQuote,
    StockReservation,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in OrderItem._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


class OrderAuditInline(admin.TabularInline):
    model = OrderAuditEvent
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in OrderAuditEvent._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "fulfillment_method",
        "identity_status",
        "payment_status",
        "fulfillment_status",
        "created_at",
    )
    list_filter = ("identity_status", "payment_status", "fulfillment_status", "fulfillment_method")
    search_fields = ("public_id", "user__email", "items__sku_snapshot")
    readonly_fields = (
        "public_id",
        "customer_snapshot",
        "address_snapshot",
        "fiscal_snapshot",
        "coupon_code_snapshot",
        "subtotal_snapshot",
        "discount_snapshot",
        "shipping_amount_snapshot",
        "shipping_quote",
        "total_snapshot",
        "created_at",
        "identity_status",
        "payment_status",
        "fulfillment_status",
    )
    inlines = (OrderItemInline, OrderAuditInline)


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("variant", "quantity", "status", "expires_at", "reference")
    list_filter = ("status",)
    search_fields = ("variant__sku", "reference")
    readonly_fields = [field.name for field in StockReservation._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("variant", "kind", "quantity_delta", "reference", "created_at")
    list_filter = ("kind",)
    search_fields = ("variant__sku", "reference")
    readonly_fields = [field.name for field in InventoryMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PromotionRule)
admin.site.register(Coupon)
admin.site.register(Cart)
admin.site.register(CartLine)
admin.site.register(IdentityVerification)
admin.site.register(PackageBox)
admin.site.register(ShippingQuote)
admin.site.register(PaymentTransaction)
admin.site.register(PaymentWebhookEvent)
admin.site.register(Shipment)
admin.site.register(Refund)
admin.site.register(NotificationAttempt)
admin.site.register(ExternalProviderFailure)
