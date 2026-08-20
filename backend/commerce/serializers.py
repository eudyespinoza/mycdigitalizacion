from rest_framework import serializers

from commerce.models import (
    CartLine,
    IdentityVerification,
    Order,
    OrderItem,
    PaymentTransaction,
    ShippingQuote,
)
from commerce.services import calculate_cart_totals


class CartPostRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)
    coupon = serializers.CharField(required=False)

    def validate(self, attrs):
        if "variant_id" not in attrs and not attrs.get("coupon"):
            raise serializers.ValidationError("Provide either variant_id or coupon")
        return attrs


class CartPatchRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class CartDeleteRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)


class CartLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="variant.sku", read_only=True)
    unit_price = serializers.DecimalField(
        source="variant.price", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartLine
        fields = ("id", "variant_id", "sku", "quantity", "unit_price")


class CartSerializer(serializers.Serializer):
    lines = CartLineSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    cart_token = serializers.SerializerMethodField()
    coupon = serializers.CharField(source="coupon.code", allow_null=True, read_only=True)

    def _totals(self, cart):
        if not hasattr(self, "_calculated_totals"):
            self._calculated_totals = calculate_cart_totals(cart)
        return self._calculated_totals

    def get_subtotal(self, cart) -> str:
        return f"{self._totals(cart).subtotal:.2f}"

    def get_discount(self, cart) -> str:
        return f"{self._totals(cart).discount:.2f}"

    def get_total(self, cart) -> str:
        return f"{self._totals(cart).total:.2f}"

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


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

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
            "created_at",
        )


class CheckoutRequestSerializer(serializers.Serializer):
    fulfillment_method = serializers.ChoiceField(choices=Order.FulfillmentMethod.choices)
    address_id = serializers.IntegerField(required=False)
    shipping_quote_id = serializers.UUIDField(required=False)


class CheckoutResponseSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    identity_status = serializers.CharField()
    payment_status = serializers.CharField()
    checkout_url = serializers.URLField(allow_blank=True)


class IdentityValidationRequestSerializer(serializers.Serializer):
    consent = serializers.BooleanField(default=True)


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
