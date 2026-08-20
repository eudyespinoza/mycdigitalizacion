from rest_framework import serializers

from landing.models import (
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
    SiteSettings,
)


class SiteSettingsSerializer(serializers.ModelSerializer):
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
        )


class ScheduledContentSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()

    def _media_url(self, file):
        return file.url if file else ""

    def get_desktop_image_url(self, instance) -> str:
        return self._media_url(instance.desktop_image)

    def get_mobile_image_url(self, instance) -> str:
        return self._media_url(instance.mobile_image)

    class Meta:
        fields = (
            "id",
            "title",
            "alt_text",
            "desktop_image_url",
            "mobile_image_url",
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
        fields = ScheduledContentSerializer.Meta.fields + ("body",)


class PromotionSlideSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = PromotionSlide
        fields = ScheduledContentSerializer.Meta.fields + ("body",)


class LandingCollectionSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = LandingCollection
        fields = ScheduledContentSerializer.Meta.fields + ("product_ids",)


class PromotionPopupSerializer(ScheduledContentSerializer):
    class Meta(ScheduledContentSerializer.Meta):
        model = PromotionPopup
        fields = ScheduledContentSerializer.Meta.fields + ("body",)


class StorefrontHomeSerializer(serializers.Serializer):
    settings = SiteSettingsSerializer()
    hero_slides = HeroSlideSerializer(many=True)
    promotion_slides = PromotionSlideSerializer(many=True)
    collections = LandingCollectionSerializer(many=True)
    promotion_popups = PromotionPopupSerializer(many=True)
