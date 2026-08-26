from rest_framework import serializers

from analytics.models import AnalyticsEvent
from catalog.models import Product, ProductVariant


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: "Este campo no está permitido." for field in sorted(unknown)}
            )
        return super().to_internal_value(data)


class AnalyticsDimensionsSerializer(StrictSerializer):
    utm_source = serializers.CharField(required=False, allow_blank=True, max_length=80)
    utm_medium = serializers.CharField(required=False, allow_blank=True, max_length=80)
    utm_campaign = serializers.CharField(required=False, allow_blank=True, max_length=120)
    referrer = serializers.URLField(required=False, allow_blank=True, max_length=500)


class AnalyticsEventInputSerializer(StrictSerializer):
    event_id = serializers.UUIDField()
    event_type = serializers.ChoiceField(choices=AnalyticsEvent.EventType.values)
    path = serializers.CharField(max_length=500, required=False, allow_blank=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=Product.objects.filter(is_active=True),
        required=False,
    )
    variant_id = serializers.PrimaryKeyRelatedField(
        source="variant",
        queryset=ProductVariant.objects.filter(is_active=True),
        required=False,
    )
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=1000)
    dimensions = AnalyticsDimensionsSerializer(required=False)

    def validate(self, attrs):
        product = attrs.get("product")
        variant = attrs.get("variant")
        if attrs["event_type"] == AnalyticsEvent.EventType.PRODUCT_VIEW and not product:
            raise serializers.ValidationError({"product_id": "El producto es obligatorio."})
        if variant and (not product or variant.product_id != product.pk):
            raise serializers.ValidationError(
                {"variant_id": "La variante no pertenece al producto indicado."}
            )
        return attrs


class AnalyticsBatchSerializer(StrictSerializer):
    events = AnalyticsEventInputSerializer(many=True, allow_empty=False, max_length=20)


class AnalyticsAcceptedSerializer(serializers.Serializer):
    accepted = serializers.IntegerField(min_value=0)
