from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import (
    BillingProfile,
    CustomerProfile,
    Profile,
    normalize_cuit,
    normalize_dni,
)


def validate_person_name(value):
    normalized = value.strip()
    if not normalized:
        raise serializers.ValidationError("This field may not be blank.")
    return normalized


def validate_phone(value):
    normalized = value.strip()
    if not 6 <= sum(character.isdigit() for character in normalized) <= 15:
        raise serializers.ValidationError("Phone must contain between 6 and 15 digits")
    if any(character not in "+-(). /0123456789" for character in normalized):
        raise serializers.ValidationError("Phone contains unsupported characters")
    return normalized


class RegistrationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    consent_version = serializers.CharField()
    first_name = serializers.CharField(
        max_length=120, required=False, default="", validators=(validate_person_name,)
    )
    last_name = serializers.CharField(
        max_length=120, required=False, default="", validators=(validate_person_name,)
    )
    phone = serializers.CharField(
        max_length=32, required=False, default="", validators=(validate_phone,)
    )

    def validate_email(self, value):
        return value.strip().casefold()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_consent_version(self, value):
        if value != settings.CURRENT_CONSENT_VERSION:
            raise serializers.ValidationError("Unsupported consent version")
        return value


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    cart_token = serializers.CharField(required=False)


class VerifyEmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(r"^\d{6}$")


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("first_name", "last_name", "phone")


class CustomerUpdateRequestSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        max_length=120, required=False, validators=(validate_person_name,)
    )
    last_name = serializers.CharField(
        max_length=120, required=False, validators=(validate_person_name,)
    )
    phone = serializers.CharField(max_length=32, required=False, validators=(validate_phone,))
    dni = serializers.CharField(write_only=True, required=False)

    def validate_dni(self, value):
        try:
            normalize_dni(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class CustomerSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    masked_dni = serializers.CharField(source="customer_profile.masked_dni", read_only=True)
    masked_cuit = serializers.CharField(source="customer_profile.masked_cuit", read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "email_verified_at",
            "is_staff",
            "profile",
            "masked_dni",
            "masked_cuit",
        )
        read_only_fields = ("is_staff",)


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

    def validate_cuit(self, value):
        try:
            normalize_cuit(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def create(self, validated_data):
        cuit = validated_data.pop("cuit", "")
        customer, _ = CustomerProfile.objects.get_or_create(
            user=self.context["request"].user,
            defaults={"consent_version": settings.CURRENT_CONSENT_VERSION},
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
