from rest_framework import serializers

from locations.models import Address


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
