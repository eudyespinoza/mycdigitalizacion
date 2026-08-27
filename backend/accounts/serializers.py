from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
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


class AuthConfigurationSerializer(serializers.Serializer):
    email_verification_required = serializers.BooleanField()
    google_enabled = serializers.BooleanField()
    google_client_id = serializers.CharField(allow_blank=True)


class GoogleAuthenticationRequestSerializer(serializers.Serializer):
    credential = serializers.CharField(max_length=8192, write_only=True)
    mode = serializers.ChoiceField(choices=("login", "register"))
    phone = serializers.CharField(
        max_length=32,
        required=False,
        default="",
        validators=(validate_phone,),
    )
    consent_version = serializers.CharField(required=False, default="")
    cart_token = serializers.CharField(required=False)

    def validate(self, attrs):
        if attrs["mode"] == "register":
            if not attrs["phone"]:
                raise serializers.ValidationError({"phone": ["Ingresá un teléfono válido."]})
            if attrs["consent_version"] != settings.CURRENT_CONSENT_VERSION:
                raise serializers.ValidationError(
                    {"consent_version": ["Aceptá la política de privacidad vigente."]}
                )
        return attrs


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
    profile = serializers.SerializerMethodField()
    masked_dni = serializers.SerializerMethodField()
    masked_cuit = serializers.SerializerMethodField()

    @extend_schema_field(ProfileSerializer)
    def get_profile(self, user):
        profile = getattr(user, "profile", None)
        if profile is None:
            return {"first_name": "", "last_name": "", "phone": ""}
        return ProfileSerializer(profile).data

    @extend_schema_field(serializers.CharField())
    def get_masked_dni(self, user):
        customer = getattr(user, "customer_profile", None)
        return customer.masked_dni if customer else ""

    @extend_schema_field(serializers.CharField())
    def get_masked_cuit(self, user):
        customer = getattr(user, "customer_profile", None)
        return customer.masked_cuit if customer else ""

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
