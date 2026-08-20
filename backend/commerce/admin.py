from urllib.parse import urlsplit

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils.html import format_html

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
    StaffExportAudit,
    StockReservation,
)
from providers import ProviderError


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


class ShipmentInline(admin.StackedInline):
    model = Shipment
    extra = 0
    max_num = 1
    can_delete = False
    fields = ("status", "tracking_number", "safe_label_link", "updated_at", "created_at")
    readonly_fields = fields

    @admin.display(description="Etiqueta")
    def safe_label_link(self, shipment):
        parsed = urlsplit(shipment.label_url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Sin etiqueta"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Abrir etiqueta</a>',
            shipment.label_url,
        )

    def has_add_permission(self, request, obj=None):
        return False


class GuardedOrderActionForm(ActionForm):
    reason = forms.CharField(
        required=True,
        max_length=500,
        label="Motivo auditable",
        widget=forms.TextInput(attrs={"size": 48}),
    )


class AppendOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        del request, obj
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        del request
        return False

    def has_change_permission(self, request, obj=None):
        del request, obj
        return False

    def has_delete_permission(self, request, obj=None):
        del request, obj
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
    inlines = (OrderItemInline, ShipmentInline, OrderAuditInline)
    actions = (
        "approve_identity_selected",
        "resume_selected",
        "cancel_selected",
        "refund_selected",
        "create_shipment_selected",
        "refresh_tracking_selected",
        "export_selected_csv",
        "export_selected_xlsx",
    )
    action_form = GuardedOrderActionForm

    def _perform_guarded(self, request, queryset, action):
        from commerce.admin_services import perform_order_admin_action
        from commerce.provider_config import get_carrier_adapter, get_payment_adapter
        from commerce.services import get_or_create_user_cart

        adapters = {}
        try:
            if action in {"resume", "refund"}:
                adapters["payment"] = get_payment_adapter()
            if action in {"create_shipment", "refresh_tracking"}:
                adapters["carrier"] = get_carrier_adapter()
        except ProviderError:
            self.message_user(
                request,
                f"{queryset.count()} pedido(s) no eran elegibles; no se modificaron.",
                messages.WARNING,
            )
            return
        completed = 0
        failed = 0
        reason = request.POST.get("reason", "")
        for order in queryset.select_related("user"):
            context = (
                {"cart": get_or_create_user_cart(user=order.user)}
                if action == "resume"
                else {}
            )
            try:
                perform_order_admin_action(
                    action=action,
                    order=order,
                    actor=request.user,
                    reason=reason,
                    adapters=adapters,
                    context=context,
                )
                completed += 1
            except (ProviderError, ValidationError):
                failed += 1
        if completed:
            self.message_user(request, f"{completed} pedido(s) procesado(s).", messages.SUCCESS)
        if failed:
            self.message_user(
                request,
                f"{failed} pedido(s) no eran elegibles; no se modificaron.",
                messages.WARNING,
            )

    @admin.action(
        description="Aprobar identidad mediante servicio guardado",
        permissions=("approve_identity_order",),
    )
    def approve_identity_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "approve_identity")

    @admin.action(
        description="Reanudar checkout mediante servicio guardado",
        permissions=("resume_order",),
    )
    def resume_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "resume")

    @admin.action(
        description="Cancelar mediante servicio guardado", permissions=("cancel_order",)
    )
    def cancel_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "cancel")

    @admin.action(
        description="Reembolsar mediante servicio guardado", permissions=("refund_order",)
    )
    def refund_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "refund")

    @admin.action(
        description="Crear envío mediante servicio guardado",
        permissions=("create_shipment_order",),
    )
    def create_shipment_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "create_shipment")

    @admin.action(
        description="Actualizar tracking mediante servicio guardado",
        permissions=("refresh_tracking_order",),
    )
    def refresh_tracking_selected(self, request, queryset):
        self._perform_guarded(request, queryset, "refresh_tracking")

    def _export(self, request, queryset, export_format):
        from commerce.exports import export_orders

        payload = export_orders(
            queryset,
            actor=request.user,
            export_format=export_format,
            filters={key: request.GET.getlist(key) for key in request.GET},
        )
        content_type = (
            "text/csv"
            if export_format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="pedidos.{export_format}"'
        return response

    @admin.action(description="Exportar pedidos a CSV", permissions=("export_order",))
    def export_selected_csv(self, request, queryset):
        return self._export(request, queryset, "csv")

    @admin.action(description="Exportar pedidos a XLSX", permissions=("export_order",))
    def export_selected_xlsx(self, request, queryset):
        return self._export(request, queryset, "xlsx")

    def has_change_permission(self, request, obj=None):
        del request, obj
        return False

    def has_add_permission(self, request):
        del request
        return False

    def has_approve_identity_order_permission(self, request):
        return request.user.has_perm("commerce.approve_identity_order")

    def has_resume_order_permission(self, request):
        return request.user.has_perm("commerce.resume_order")

    def has_cancel_order_permission(self, request):
        return request.user.has_perm("commerce.cancel_order")

    def has_refund_order_permission(self, request):
        return request.user.has_perm("commerce.refund_order")

    def has_create_shipment_order_permission(self, request):
        return request.user.has_perm("commerce.create_shipment_order")

    def has_refresh_tracking_order_permission(self, request):
        return request.user.has_perm("commerce.refresh_tracking_order")

    def has_export_order_permission(self, request):
        return request.user.has_perm("commerce.export_order")


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
admin.site.register(IdentityVerification, AppendOnlyAdmin)
admin.site.register(PackageBox)
admin.site.register(ShippingQuote)
admin.site.register(PaymentTransaction, AppendOnlyAdmin)
admin.site.register(PaymentWebhookEvent, AppendOnlyAdmin)
admin.site.register(Shipment, AppendOnlyAdmin)
admin.site.register(Refund, AppendOnlyAdmin)
admin.site.register(NotificationAttempt, AppendOnlyAdmin)
admin.site.register(ExternalProviderFailure, AppendOnlyAdmin)
admin.site.register(StaffExportAudit, AppendOnlyAdmin)
