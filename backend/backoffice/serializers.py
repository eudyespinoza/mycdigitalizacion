from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from rest_framework import serializers

from landing.models import SiteSettings, normalize_whatsapp_number


class ManagementUserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "permissions",
        )

    def get_permissions(self, user) -> list[str]:
        return sorted(user.get_all_permissions())


class IntegrationUpdateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    environment = serializers.ChoiceField(
        choices=("sandbox", "qa", "production"), required=False
    )
    public_config = serializers.DictField(required=False)
    secrets = serializers.DictField(required=False, write_only=True)
    clear_secret_fields = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    def validate(self, attrs):
        definition = self.context["definition"]
        public_config = attrs.get("public_config", {})
        secrets = attrs.get("secrets", {})
        clear_fields = attrs.get("clear_secret_fields", [])
        unknown_public = set(public_config) - set(definition.public_fields)
        unknown_secrets = set(secrets) - set(definition.secret_fields)
        unknown_clear = set(clear_fields) - set(definition.secret_fields)
        if unknown_public or unknown_secrets or unknown_clear:
            raise serializers.ValidationError(
                "La configuración contiene campos que no corresponden a esta integración."
            )
        return attrs


class GeneralSettingsSerializer(serializers.ModelSerializer):
    whatsapp_number = serializers.CharField(
        allow_blank=True,
        max_length=32,
        required=False,
    )
    logo_url = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()

    def get_logo_url(self, settings) -> str:
        return settings.logo.url if settings.logo else "/brand/mycdigitalizacion-logo.png"

    def get_favicon_url(self, settings) -> str:
        return settings.favicon.url if settings.favicon else "/brand/mycdigitalizacion-logo.png"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}
        for field_name in (
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "youtube_url",
            "linkedin_url",
        ):
            value = attrs.get(field_name)
            if value and urlsplit(value).scheme != "https":
                errors[field_name] = "La dirección debe comenzar con https://"
        enabled = attrs.get(
            "whatsapp_enabled",
            getattr(self.instance, "whatsapp_enabled", False),
        )
        number = normalize_whatsapp_number(
            attrs.get(
                "whatsapp_number",
                getattr(self.instance, "whatsapp_number", ""),
            )
        )
        attrs["whatsapp_number"] = number
        if enabled and not 8 <= len(number) <= 15:
            errors["whatsapp_number"] = (
                "Ingresá un número internacional de 8 a 15 dígitos."
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    class Meta:
        model = SiteSettings
        fields = (
            "public_name",
            "announcement",
            "contact_email",
            "pickup_enabled",
            "pickup_label",
            "pickup_address",
            "pickup_hours",
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "youtube_url",
            "linkedin_url",
            "whatsapp_enabled",
            "whatsapp_number",
            "whatsapp_message",
            "logo",
            "favicon",
            "logo_url",
            "favicon_url",
        )
        extra_kwargs = {
            "logo": {"write_only": True, "required": False},
            "favicon": {"write_only": True, "required": False},
        }


class ManagementSessionResponseSerializer(serializers.Serializer):
    user = ManagementUserSerializer()


class ManagementDashboardMetricsSerializer(serializers.Serializer):
    active_products = serializers.IntegerField(min_value=0)
    low_stock_variants = serializers.IntegerField(min_value=0)
    orders_requiring_attention = serializers.IntegerField(min_value=0)
    integration_incidents = serializers.IntegerField(min_value=0)


class ManagementDashboardResponseSerializer(serializers.Serializer):
    metrics = ManagementDashboardMetricsSerializer()


class IntegrationConfigurationResponseSerializer(serializers.Serializer):
    provider = serializers.CharField()
    label = serializers.CharField()
    enabled = serializers.BooleanField()
    environment = serializers.CharField()
    status = serializers.CharField()
    public_config = serializers.JSONField()
    secret_fields = serializers.DictField(child=serializers.BooleanField())
    version = serializers.IntegerField(min_value=0)
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by = serializers.CharField(allow_blank=True)
    last_test_status = serializers.CharField(allow_blank=True)
    last_tested_at = serializers.DateTimeField(allow_null=True)
    last_test_message = serializers.CharField(allow_blank=True)


class IntegrationListResponseSerializer(serializers.Serializer):
    results = IntegrationConfigurationResponseSerializer(many=True)
