from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from commerce.models import (
    IdentityVerification,
    Order,
    OrderItem,
    PaymentTransaction,
    ShippingQuote,
)
from commerce.services import money, price_cart_lines, purchase_quantity_limit
from landing.models import SiteSettings


class CartPostRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=settings.MAX_CART_LINE_QUANTITY,
        required=False,
        default=1,
    )
    coupon = serializers.CharField(required=False)

    def validate(self, attrs):
        if "variant_id" not in attrs and not attrs.get("coupon"):
            raise serializers.ValidationError("Provide either variant_id or coupon")
        return attrs


class CartPatchRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(
        min_value=0,
        max_value=settings.MAX_CART_LINE_QUANTITY,
    )


class CartDeleteRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)


class CartLineNoticeSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=("price_changed", "stock_changed"))
    previous = serializers.JSONField()
    current = serializers.JSONField()


class CartLineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    sku = serializers.CharField()
    product_name = serializers.CharField()
    variant_name = serializers.CharField(allow_blank=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    availability = serializers.ChoiceField(
        choices=("available", "insufficient_stock", "unavailable")
    )
    available_stock = serializers.IntegerField()
    stock_is_infinite = serializers.BooleanField()
    purchase_limit = serializers.IntegerField(allow_null=True)
    notices = CartLineNoticeSerializer(many=True)


class CartSerializer(serializers.Serializer):
    lines = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    cart_token = serializers.SerializerMethodField()
    coupon = serializers.CharField(source="coupon.code", allow_null=True, read_only=True)

    def _priced(self, cart):
        if not hasattr(self, "_priced_lines"):
            lines = list(
                cart.lines.select_related("variant__product__category").order_by("pk")
            )
            self._priced_lines = price_cart_lines(lines, coupon=cart.coupon)
        return self._priced_lines

    @extend_schema_field(CartLineSerializer(many=True))
    def get_lines(self, cart):
        payload = []
        for priced in self._priced(cart):
            line = priced.cart_line
            variant = line.variant
            stock = variant.available_stock
            purchase_limit = purchase_quantity_limit(variant)
            available = (
                variant.is_active
                and variant.product.is_active
                and variant.product.is_sellable
            )
            availability = (
                "unavailable"
                if not available
                else "insufficient_stock"
                if purchase_limit is not None and purchase_limit < line.quantity
                else "available"
            )
            notices = []
            if (
                line.unit_price_snapshot is not None
                and line.unit_price_snapshot != variant.price
            ):
                notices.append(
                    {
                        "code": "price_changed",
                        "previous": f"{line.unit_price_snapshot:.2f}",
                        "current": f"{variant.price:.2f}",
                    }
                )
            if (
                line.available_stock_snapshot is not None
                and line.available_stock_snapshot != purchase_limit
            ):
                notices.append(
                    {
                        "code": "stock_changed",
                        "previous": line.available_stock_snapshot,
                        "current": purchase_limit,
                    }
                )
            payload.append(
                {
                    "id": line.pk,
                    "variant_id": line.variant_id,
                    "sku": variant.sku,
                    "product_name": variant.product.name,
                    "variant_name": variant.name,
                    "quantity": line.quantity,
                    "unit_price": f"{variant.price:.2f}",
                    "line_subtotal": f"{priced.subtotal:.2f}",
                    "line_discount": f"{priced.discount:.2f}",
                    "line_total": f"{priced.total:.2f}",
                    "availability": availability,
                    "available_stock": stock,
                    "stock_is_infinite": variant.stock_is_infinite,
                    "purchase_limit": purchase_limit,
                    "notices": notices,
                }
            )
        return payload

    def _totals(self, cart):
        priced = self._priced(cart)
        subtotal = money(sum((line.subtotal for line in priced), Decimal("0")))
        discount = money(sum((line.discount for line in priced), Decimal("0")))
        return subtotal, discount, money(subtotal - discount)

    def get_subtotal(self, cart) -> str:
        return f"{self._totals(cart)[0]:.2f}"

    def get_discount(self, cart) -> str:
        return f"{self._totals(cart)[1]:.2f}"

    def get_total(self, cart) -> str:
        return f"{self._totals(cart)[2]:.2f}"

    def get_cart_token(self, cart) -> str | None:
        return None if cart.user_id else cart.signed_token


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "product_name_snapshot",
            "variant_name_snapshot",
            "sku_snapshot",
            "quantity",
            "unit_price_snapshot",
            "discount_snapshot",
            "line_total_snapshot",
        )


class PublicFiscalSnapshotSerializer(serializers.Serializer):
    label = serializers.CharField(read_only=True)
    legal_name = serializers.CharField(read_only=True)
    tax_condition = serializers.CharField(read_only=True)
    masked_cuit = serializers.CharField(read_only=True)


class PublicTimelineEventSerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField()
    occurred_at = serializers.DateTimeField()


class PublicShipmentSerializer(serializers.Serializer):
    carrier = serializers.CharField()
    tracking_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    updated_at = serializers.DateTimeField()


class PublicPickupInformationSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    label = serializers.CharField()
    address = serializers.CharField(allow_blank=True)
    hours = serializers.CharField(allow_blank=True)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    fiscal_snapshot = PublicFiscalSnapshotSerializer(read_only=True)
    timeline = serializers.SerializerMethodField()
    shipment = serializers.SerializerMethodField()
    pickup_information = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "public_id",
            "identity_status",
            "payment_status",
            "fulfillment_status",
            "fulfillment_method",
            "customer_snapshot",
            "address_snapshot",
            "fiscal_snapshot",
            "coupon_code_snapshot",
            "subtotal_snapshot",
            "discount_snapshot",
            "shipping_amount_snapshot",
            "total_snapshot",
            "items",
            "timeline",
            "shipment",
            "pickup_information",
            "created_at",
        )

    @extend_schema_field(PublicTimelineEventSerializer(many=True))
    def get_timeline(self, order):
        labels = {
            "order_created": "Pedido creado",
            "identity_pending_identity": "Identidad pendiente",
            "identity_verified": "Identidad verificada",
            "identity_manual_review": "Identidad en revisión",
            "payment_not_started": "Pago no iniciado",
            "payment_pending": "Pago pendiente",
            "payment_paid": "Pago acreditado",
            "payment_failed": "Pago rechazado",
            "payment_refunded": "Pago reintegrado",
            "payment_needs_attention": "Pago requiere atención",
            "fulfillment_unfulfilled": "Preparación pendiente",
            "fulfillment_preparing": "Pedido en preparación",
            "fulfillment_shipped": "Pedido despachado",
            "fulfillment_ready_for_pickup": "Listo para retirar",
            "fulfillment_fulfilled": "Pedido entregado",
        }
        events = []
        for event in order.audit_events.order_by("created_at", "pk"):
            if event.kind == "created_pending_identity":
                public_status = "order_created"
            elif event.kind in {
                "identity_status_changed",
                "payment_status_changed",
                "fulfillment_status_changed",
            }:
                prefix = event.kind.removesuffix("_status_changed")
                value = event.data.get("to")
                public_status = f"{prefix}_{value}"
            else:
                continue
            if public_status not in labels:
                continue
            events.append(
                {
                    "status": public_status,
                    "label": labels[public_status],
                    "occurred_at": event.created_at,
                }
            )
            if len(events) == 50:
                break
        return events

    @extend_schema_field(PublicShipmentSerializer(allow_null=True))
    def get_shipment(self, order):
        try:
            shipment = order.shipment
        except ObjectDoesNotExist:
            return None
        return {
            "carrier": shipment.provider,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "updated_at": shipment.updated_at,
        }

    @extend_schema_field(PublicPickupInformationSerializer(allow_null=True))
    def get_pickup_information(self, order):
        if order.fulfillment_method != Order.FulfillmentMethod.PICKUP:
            return None
        settings = SiteSettings.objects.first()
        return {
            "enabled": settings.pickup_enabled if settings else True,
            "label": settings.pickup_label if settings else "Retiro en tienda",
            "address": settings.pickup_address if settings else "",
            "hours": settings.pickup_hours if settings else "",
        }


class CheckoutRequestSerializer(serializers.Serializer):
    fulfillment_method = serializers.ChoiceField(choices=Order.FulfillmentMethod.choices)
    address_id = serializers.IntegerField(required=False)
    shipping_quote_id = serializers.UUIDField(required=False)
    billing_profile_id = serializers.IntegerField()
    consent = serializers.BooleanField()
    idempotency_key = serializers.UUIDField()


class CheckoutResponseSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    identity_status = serializers.CharField()
    payment_status = serializers.CharField()
    checkout_url = serializers.URLField(allow_blank=True)


class IdentityValidationRequestSerializer(serializers.Serializer):
    consent = serializers.BooleanField()


class ManualIdentityReviewSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1, max_length=1000)


class IdentityVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityVerification
        fields = ("id", "status", "masked_audit", "created_at", "reviewed_at")


class ShippingQuoteRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()


class ShippingQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingQuote
        fields = (
            "public_id",
            "service",
            "parcels",
            "base_amount",
            "surcharge_amount",
            "total_amount",
            "currency",
            "expires_at",
        )


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ("external_reference", "status", "payment_id", "amount", "currency")


class RefundRequestSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()


class ShipmentResponseSerializer(serializers.Serializer):
    provider_id = serializers.CharField()
    tracking_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()


class LabelResponseSerializer(serializers.Serializer):
    label_url = serializers.URLField(allow_blank=True)


class RefundResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    stock_restored = serializers.BooleanField()
    return_required = serializers.BooleanField()
