from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import APIException

from catalog.models import Category, Product
from commerce.models import Coupon, CouponRedemption, PromotionRule
from config.api_serializers import ResponsiveMediaSourceSerializer
from config.media import public_derivative_sources
from landing.models import (
    CatalogSlide,
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
)


class PromotionScopeOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    description = serializers.CharField(required=False)


class PromotionScopeOptionsSerializer(serializers.Serializer):
    products = PromotionScopeOptionSerializer(many=True)
    categories = PromotionScopeOptionSerializer(many=True)


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


class ManagementCatalogSlideSerializer(ManagementScheduledContentSerializer):
    class Meta(ManagementScheduledContentSerializer.Meta):
        model = CatalogSlide
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


class OfferScopeConflict(APIException):
    status_code = 400

    def __init__(self, detail):
        super().__init__({"code": "offer_scope_conflict", "detail": detail})


def lock_offer_scope_writes():
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [6_217_004])
        return
    list(PromotionRule.objects.select_for_update().values_list("pk", flat=True))


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

    def validate(self, attrs):
        instance = self.instance
        enabled = attrs.get("enabled", instance.enabled if instance else True)
        if not enabled:
            return attrs
        starts_at = attrs.get("starts_at", instance.starts_at if instance else None)
        ends_at = attrs.get("ends_at", instance.ends_at if instance else None)
        products = attrs.get(
            "products",
            list(instance.products.all()) if instance else [],
        )
        categories = attrs.get(
            "categories",
            list(instance.categories.all()) if instance else [],
        )
        if not starts_at or not ends_at:
            return attrs

        product_ids = {product.pk for product in products}
        category_ids = {category.pk for category in categories}
        product_category_ids = {product.category_id for product in products}
        overlapping = PromotionRule.objects.filter(
            enabled=True,
            starts_at__lte=ends_at,
            ends_at__gte=starts_at,
        )
        if instance:
            overlapping = overlapping.exclude(pk=instance.pk)
        conflicting = overlapping.filter(
            Q(products__pk__in=product_ids)
            | Q(categories__pk__in=category_ids)
            | Q(categories__pk__in=product_category_ids)
            | Q(products__category_id__in=category_ids)
        ).exists()
        if conflicting:
            raise OfferScopeConflict(
                "Ese producto o categoría ya pertenece a otra oferta "
                "durante la vigencia seleccionada."
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lock_offer_scope_writes()
        self.validate(validated_data)
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        lock_offer_scope_writes()
        self.validate(validated_data)
        return super().update(instance, validated_data)


class ManagementCouponSerializer(serializers.ModelSerializer):
    used_redemptions = serializers.SerializerMethodField()
    reserved_redemptions = serializers.SerializerMethodField()

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
            "max_redemptions",
            "used_redemptions",
            "reserved_redemptions",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_used_redemptions(self, coupon):
        annotated = getattr(coupon, "used_redemptions_value", None)
        if annotated is not None:
            return annotated
        return coupon.redemptions.filter(
            status=CouponRedemption.Status.CONSUMED
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_reserved_redemptions(self, coupon):
        annotated = getattr(coupon, "reserved_redemptions_value", None)
        if annotated is not None:
            return annotated
        return coupon.redemptions.filter(
            status=CouponRedemption.Status.RESERVED,
            expires_at__gt=timezone.now(),
        ).count()
