from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Category, Product
from commerce.models import Coupon, PromotionRule
from config.api_serializers import ResponsiveMediaSourceSerializer
from config.media import public_derivative_sources
from landing.models import (
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
)


class ManagementScheduledContentSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()
    desktop_responsive_sources = serializers.SerializerMethodField()
    mobile_responsive_sources = serializers.SerializerMethodField()

    def get_desktop_image_url(self, instance) -> str:
        return instance.desktop_image.url if instance.desktop_image else ""

    def get_mobile_image_url(self, instance) -> str:
        return instance.mobile_image.url if instance.mobile_image else ""

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
            "enabled",
            "order",
            "starts_at",
            "ends_at",
            "desktop_image",
            "mobile_image",
            "desktop_image_url",
            "mobile_image_url",
            "desktop_responsive_sources",
            "mobile_responsive_sources",
            "alt_text",
            "cta_label",
            "cta_url",
            "focal_x",
            "focal_y",
            "safe_height_mobile",
            "safe_height_tablet",
            "safe_height_desktop",
        )
        extra_kwargs = {
            "desktop_image": {"write_only": True, "required": False},
            "mobile_image": {"write_only": True, "required": False},
        }


class ManagementHeroSerializer(ManagementScheduledContentSerializer):
    class Meta(ManagementScheduledContentSerializer.Meta):
        model = HeroSlide
        fields = ManagementScheduledContentSerializer.Meta.fields + (
            "body",
            "interval_ms",
            "pause_on_reduced_motion",
        )


class ManagementPromotionSlideSerializer(ManagementScheduledContentSerializer):
    class Meta(ManagementScheduledContentSerializer.Meta):
        model = PromotionSlide
        fields = ManagementScheduledContentSerializer.Meta.fields + (
            "body",
            "interval_ms",
            "pause_on_reduced_motion",
        )


class ManagementCollectionSerializer(ManagementScheduledContentSerializer):
    class Meta(ManagementScheduledContentSerializer.Meta):
        model = LandingCollection
        fields = ManagementScheduledContentSerializer.Meta.fields + ("product_ids",)


class ManagementPopupSerializer(ManagementScheduledContentSerializer):
    class Meta(ManagementScheduledContentSerializer.Meta):
        model = PromotionPopup
        fields = ManagementScheduledContentSerializer.Meta.fields + (
            "body",
            "frequency",
            "display_delay_ms",
            "dismissible",
            "version",
        )


class ManagementPromotionRuleSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(
        source="products", many=True, queryset=Product.objects.all(), required=False
    )
    category_ids = serializers.PrimaryKeyRelatedField(
        source="categories", many=True, queryset=Category.objects.all(), required=False
    )

    class Meta:
        model = PromotionRule
        fields = (
            "id",
            "name",
            "discount_type",
            "value",
            "starts_at",
            "ends_at",
            "enabled",
            "product_ids",
            "category_ids",
        )


class ManagementCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "discount_type",
            "value",
            "starts_at",
            "ends_at",
            "enabled",
            "combinable",
        )
