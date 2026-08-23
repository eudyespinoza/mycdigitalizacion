from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from config.api_serializers import ResponsiveMediaSourceSerializer
from config.media import public_derivative_sources
from landing.models import (
    CatalogSlide,
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
    SiteSettings,
)


class SiteSettingsSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    logo_responsive_sources = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()

    def get_logo_url(self, instance) -> str:
        return instance.logo.url if instance.logo else "/brand/mycdigitalizacion-logo.png"

    @extend_schema_field(ResponsiveMediaSourceSerializer(many=True))
    def get_logo_responsive_sources(self, instance):
        return public_derivative_sources(
            storage=instance.logo.storage,
            derivatives=instance.logo_derivatives,
        )

    def get_favicon_url(self, instance) -> str:
        return instance.favicon.url if instance.favicon else "/brand/mycdigitalizacion-logo.png"

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
            "theme_palette",
            "theme_structure",
            "theme_action",
            "theme_wayfinding",
            "theme_background",
            "theme_text",
            "logo_url",
            "logo_responsive_sources",
            "favicon_url",
        )


class ScheduledContentSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()
    desktop_responsive_sources = serializers.SerializerMethodField()
    mobile_responsive_sources = serializers.SerializerMethodField()

    def _media_url(self, file):
        return file.url if file else ""

    def get_desktop_image_url(self, instance) -> str:
        return self._media_url(instance.desktop_image)

    def get_mobile_image_url(self, instance) -> str:
        return self._media_url(instance.mobile_image)

    @extend_schema_field(ResponsiveMediaSourceSerializer(many=True))
    def get_desktop_responsive_sources(self, instance):
        return public_derivative_sources(
            storage=instance.desktop_image.storage,
            derivatives=instance.desktop_derivatives,
        )

    @extend_schema_field(ResponsiveMediaSourceSerializer(many=True))
    def get_mobile_responsive_sources(self, instance):
        return public_derivative_sources(
            storage=instance.mobile_image.storage,
            derivatives=instance.mobile_derivatives,
        )

    class Meta:
        fields = (
            "id",
            "title",
            "alt_text",
            "desktop_image_url",
            "mobile_image_url",
            "desktop_responsive_sources",
            "mobile_responsive_sources",
            "cta_label",
            "cta_url",
            "focal_x",
            "focal_y",
            "safe_height_mobile",
            "safe_height_tablet",
            "safe_height_desktop",
            "starts_at",
            "ends_at",
            "order",
        )


class HeroSlideSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = HeroSlide
        fields = ScheduledContentSerializer.Meta.fields + (
            "body",
            "interval_ms",
            "pause_on_reduced_motion",
        )


class PromotionSlideSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = PromotionSlide
        fields = ScheduledContentSerializer.Meta.fields + (
            "body",
            "interval_ms",
            "pause_on_reduced_motion",
        )


class CatalogSlideSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = CatalogSlide
        fields = ScheduledContentSerializer.Meta.fields + (
            "body",
            "interval_ms",
            "pause_on_reduced_motion",
        )


class CatalogContentSerializer(serializers.Serializer):
    slides = CatalogSlideSerializer(many=True)


class LandingCollectionSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = LandingCollection
        fields = ScheduledContentSerializer.Meta.fields + ("product_ids",)


class PromotionPopupSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = PromotionPopup
        fields = ScheduledContentSerializer.Meta.fields + (
            "body",
            "frequency",
            "display_delay_ms",
            "dismissible",
            "version",
        )


class StorefrontHomeSerializer(serializers.Serializer):
    settings = SiteSettingsSerializer()
    hero_slides = HeroSlideSerializer(many=True)
    promotion_slides = PromotionSlideSerializer(many=True)
    collections = LandingCollectionSerializer(many=True)
    promotion_popups = PromotionPopupSerializer(many=True)
