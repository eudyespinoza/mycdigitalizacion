from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Category, Product, ProductMedia, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent_id")


class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ("file", "alt_text", "order")


class PublicVariantSerializer(serializers.ModelSerializer):
    volume_cm3 = serializers.DecimalField(max_digits=27, decimal_places=6, read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "name",
            "price",
            "packaged_weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
            "volume_cm3",
        )


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    variants = serializers.SerializerMethodField()
    media = ProductMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "slug", "description", "category", "variants", "media")

    @extend_schema_field(PublicVariantSerializer(many=True))
    def get_variants(self, product):
        return PublicVariantSerializer(product.variants.filter(is_active=True), many=True).data
