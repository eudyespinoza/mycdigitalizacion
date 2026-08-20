from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import BillingProfile, CustomerProfile, Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("first_name", "last_name", "phone")


class CustomerSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    masked_dni = serializers.CharField(source="customer_profile.masked_dni", read_only=True)
    masked_cuit = serializers.CharField(source="customer_profile.masked_cuit", read_only=True)

    class Meta:
        model = get_user_model()
        fields = ("id", "email", "email_verified_at", "profile", "masked_dni", "masked_cuit")


class BillingProfileSerializer(serializers.ModelSerializer):
    masked_cuit = serializers.CharField(read_only=True)
    cuit = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = BillingProfile
        fields = (
            "id",
            "label",
            "legal_name",
            "tax_condition",
            "is_default",
            "masked_cuit",
            "cuit",
        )

    def create(self, validated_data):
        cuit = validated_data.pop("cuit", "")
        customer, _ = CustomerProfile.objects.get_or_create(
            user=self.context["request"].user, defaults={"consent_version": "api-v1"}
        )
        profile = BillingProfile(customer=customer, **validated_data)
        if cuit:
            profile.set_cuit(cuit)
        profile.save()
        return profile

    def update(self, instance, validated_data):
        cuit = validated_data.pop("cuit", "")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if cuit:
            instance.set_cuit(cuit)
        instance.save()
        return instance
