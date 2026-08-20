from django.contrib import admin

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


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in OrderItem._meta.fields]


class OrderAuditInline(admin.TabularInline):
    model = OrderAuditEvent
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in OrderAuditEvent._meta.fields]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
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
        "subtotal_snapshot",
        "discount_snapshot",
        "total_snapshot",
        "created_at",
    )
    inlines = (OrderItemInline, OrderAuditInline)


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("variant", "quantity", "status", "expires_at", "reference")
    list_filter = ("status",)
    search_fields = ("variant__sku", "reference")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("variant", "kind", "quantity_delta", "reference", "created_at")
    list_filter = ("kind",)
    search_fields = ("variant__sku", "reference")
    readonly_fields = [field.name for field in InventoryMovement._meta.fields]


admin.site.register(PromotionRule)
admin.site.register(Coupon)
admin.site.register(Cart)
admin.site.register(CartLine)
