from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import BillingProfile
from commerce.models import Order, PackageBox
from locations.models import Address


class ManagementCustomerSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    phone = serializers.CharField(source="profile.phone", default="", read_only=True)
    masked_dni = serializers.CharField(
        source="customer_profile.masked_dni", default="", read_only=True
    )
    email_verified = serializers.SerializerMethodField()
    order_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "masked_dni",
            "email_verified",
            "order_count",
            "total_spent",
        )

    def get_name(self, user) -> str:
        profile = getattr(user, "profile", None)
        name = " ".join(
            part
            for part in (
                getattr(profile, "first_name", ""),
                getattr(profile, "last_name", ""),
            )
            if part
        )
        return name or user.email

    def get_email_verified(self, user) -> bool:
        return user.email_verified_at is not None


class ManagementOrderCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_blank=True)


class ManagementOrderSummarySerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    total = serializers.DecimalField(source="total_snapshot", max_digits=12, decimal_places=2)

    class Meta:
        model = Order
        fields = (
            "public_id",
            "customer",
            "identity_status",
            "payment_status",
            "fulfillment_status",
            "fulfillment_method",
            "total",
            "created_at",
        )

    @extend_schema_field(ManagementOrderCustomerSerializer)
    def get_customer(self, order):
        profile = getattr(order.user, "profile", None)
        snapshot = order.customer_snapshot or {}
        name = snapshot.get("name") or " ".join(
            part
            for part in (
                getattr(profile, "first_name", ""),
                getattr(profile, "last_name", ""),
            )
            if part
        )
        return {
            "id": order.user_id,
            "name": name or order.user.email,
            "email": snapshot.get("email") or order.user.email,
            "phone": snapshot.get("phone") or getattr(profile, "phone", ""),
        }


class ManagementOrderItemSerializer(serializers.Serializer):
    product_name = serializers.CharField(source="product_name_snapshot")
    variant_name = serializers.CharField(source="variant_name_snapshot", allow_blank=True)
    sku = serializers.CharField(source="sku_snapshot")
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(
        source="unit_price_snapshot", max_digits=12, decimal_places=2
    )
    discount = serializers.DecimalField(
        source="discount_snapshot", max_digits=12, decimal_places=2
    )
    total = serializers.DecimalField(
        source="line_total_snapshot", max_digits=12, decimal_places=2
    )


class ManagementOrderAuditSerializer(serializers.Serializer):
    kind = serializers.CharField()
    data = serializers.JSONField()
    actor = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_actor(self, event) -> str:
        return event.actor.email if event.actor else "Sistema"


class ManagementPaymentSerializer(serializers.Serializer):
    provider = serializers.CharField()
    status = serializers.CharField()
    provider_status = serializers.CharField(allow_blank=True)
    payment_id = serializers.CharField(allow_blank=True, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    created_at = serializers.DateTimeField()


class ManagementShipmentSerializer(serializers.Serializer):
    provider = serializers.CharField()
    tracking_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    label_url = serializers.URLField(allow_blank=True)
    updated_at = serializers.DateTimeField()


class ManagementOrderDetailSerializer(ManagementOrderSummarySerializer):
    items = ManagementOrderItemSerializer(many=True, read_only=True)
    audit_events = ManagementOrderAuditSerializer(many=True, read_only=True)
    payments = ManagementPaymentSerializer(
        many=True, read_only=True, source="payment_transactions"
    )
    shipment = serializers.SerializerMethodField()
    customer_snapshot = serializers.JSONField()
    address_snapshot = serializers.JSONField()
    fiscal_snapshot = serializers.JSONField()
    subtotal = serializers.DecimalField(
        source="subtotal_snapshot", max_digits=12, decimal_places=2
    )
    discount = serializers.DecimalField(
        source="discount_snapshot", max_digits=12, decimal_places=2
    )
    shipping_amount = serializers.DecimalField(
        source="shipping_amount_snapshot", max_digits=12, decimal_places=2
    )

    class Meta(ManagementOrderSummarySerializer.Meta):
        fields = ManagementOrderSummarySerializer.Meta.fields + (
            "customer_snapshot",
            "address_snapshot",
            "fiscal_snapshot",
            "subtotal",
            "discount",
            "shipping_amount",
            "items",
            "audit_events",
            "payments",
            "shipment",
        )

    @extend_schema_field(ManagementShipmentSerializer(allow_null=True))
    def get_shipment(self, order):
        shipment = getattr(order, "management_shipment", None)
        return ManagementShipmentSerializer(shipment).data if shipment else None


class ManagementOrderActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=(
            "approve_identity",
            "cancel",
            "refund",
            "create_shipment",
            "refresh_tracking",
            "mark_preparing",
            "mark_ready_for_pickup",
            "mark_fulfilled",
        )
    )
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


class ManagementAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "raw_address",
            "normalized_address",
            "street",
            "number",
            "postal_code",
            "locality",
            "province",
            "floor",
            "apartment",
            "reference",
            "needs_review",
        )


class ManagementBillingProfileSerializer(serializers.ModelSerializer):
    masked_cuit = serializers.CharField(read_only=True)

    class Meta:
        model = BillingProfile
        fields = ("id", "label", "legal_name", "tax_condition", "masked_cuit", "is_default")


class ManagementCustomerDetailSerializer(ManagementCustomerSummarySerializer):
    addresses = ManagementAddressSerializer(many=True, read_only=True)
    billing_profiles = serializers.SerializerMethodField()
    orders = serializers.SerializerMethodField()

    class Meta(ManagementCustomerSummarySerializer.Meta):
        fields = ManagementCustomerSummarySerializer.Meta.fields + (
            "addresses",
            "billing_profiles",
            "orders",
        )

    @extend_schema_field(ManagementBillingProfileSerializer(many=True))
    def get_billing_profiles(self, user):
        customer_profile = getattr(user, "customer_profile", None)
        profiles = customer_profile.billing_profiles.all() if customer_profile else []
        return ManagementBillingProfileSerializer(profiles, many=True).data

    @extend_schema_field(ManagementOrderSummarySerializer(many=True))
    def get_orders(self, user):
        return ManagementOrderSummarySerializer(user.orders.order_by("-created_at"), many=True).data


class PackageBoxSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageBox
        fields = (
            "id",
            "code",
            "inner_length_cm",
            "inner_width_cm",
            "inner_height_cm",
            "tare_weight_grams",
            "max_weight_grams",
            "enabled",
        )

    def validate(self, attrs):
        tare = attrs.get("tare_weight_grams", getattr(self.instance, "tare_weight_grams", 0))
        maximum = attrs.get("max_weight_grams", getattr(self.instance, "max_weight_grams", 0))
        if maximum <= tare:
            raise serializers.ValidationError(
                "El peso máximo debe ser mayor que la tara del embalaje."
            )
        return attrs
