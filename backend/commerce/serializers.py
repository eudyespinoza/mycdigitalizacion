from rest_framework import serializers

from commerce.models import CartLine, Order, OrderItem
from commerce.services import calculate_cart_totals


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
            "total_snapshot",
            "items",
            "created_at",
        )
