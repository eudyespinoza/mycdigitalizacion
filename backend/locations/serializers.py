from rest_framework import serializers

from locations.models import Address, PostalLocality


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        exclude = ("user",)
        read_only_fields = (
            "normalized_address",
            "geocode_source",
            "geocode_confidence",
            "needs_review",
            "reviewed_at",
            "created_at",
            "updated_at",
        )


class PostalLookupQuerySerializer(serializers.Serializer):
    postal_code = serializers.CharField(max_length=8)


class PostalLocalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalLocality
        fields = ("postal_code", "cpa", "locality", "province")


class GeocodeRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()


class ReverseGeocodeRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)


class ReverseGeocodeResponseSerializer(serializers.Serializer):
    address = AddressSerializer()
    location = serializers.JSONField()


class AddressConfirmRequestSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    address_choice = serializers.ChoiceField(choices=("written", "reverse"))
