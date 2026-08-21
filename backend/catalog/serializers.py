from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Brand, Category, Product, ProductMedia, ProductVariant
from commerce.services import best_automatic_discount, money, purchase_quantity_limit
from config.api_serializers import ResponsiveMediaSourceSerializer
from config.media import public_derivative_sources


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent_id")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("name", "slug")


class ProductMediaSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()
    responsive_sources = serializers.SerializerMethodField()
    variant_id = serializers.IntegerField(read_only=True, allow_null=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True, default="")

    @extend_schema_field(serializers.CharField())
    def get_file(self, instance):
        return instance.file.url if instance.file else ""

    @extend_schema_field(ResponsiveMediaSourceSerializer(many=True))
    def get_responsive_sources(self, instance):
        return public_derivative_sources(
            storage=instance.file.storage,
            derivatives=instance.derivatives,
        )

    class Meta:
        model = ProductMedia
        fields = (
            "file",
            "responsive_sources",
            "alt_text",
            "order",
            "variant_id",
            "variant_name",
        )


class PublicAttributeSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    type = serializers.ChoiceField(choices=("text", "integer", "decimal", "boolean", "option"))
    value = serializers.JSONField()


class PublicPricingSerializer(serializers.Serializer):
    list_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_percentage = serializers.DecimalField(max_digits=7, decimal_places=2)
    on_offer = serializers.BooleanField()


def attribute_public_value(attribute):
    value_type = attribute.definition.value_type
    if value_type == "option":
        return attribute.option.value
    return getattr(attribute, f"{value_type}_value")


def variant_pricing(variant):
    list_price = money(variant.price)
    discount = best_automatic_discount(variant=variant, quantity=1)
    effective = money(list_price - discount)
    percentage = (
        money(discount * Decimal("100") / list_price) if list_price else Decimal("0.00")
    )
    return {
        "list_price": list_price,
        "effective_price": effective,
        "discount_amount": discount,
        "discount_percentage": percentage,
        "on_offer": discount > 0,
    }


def variant_available_stock(variant):
    annotated = getattr(variant, "available_stock_value", None)
    return annotated if annotated is not None else variant.available_stock


class PublicVariantSerializer(serializers.ModelSerializer):
    volume_cm3 = serializers.DecimalField(max_digits=27, decimal_places=6, read_only=True)
    available_stock = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    pricing = serializers.SerializerMethodField()
    purchase_limit = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "name",
            "price",
            "available_stock",
            "is_available",
            "stock_is_infinite",
            "purchase_limit",
            "packaged_weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
            "volume_cm3",
            "attributes",
            "pricing",
        )

    @extend_schema_field(PublicAttributeSerializer(many=True))
    def get_attributes(self, variant):
        values = []
        for attribute in variant.attribute_values.all():
            definition = attribute.definition
            if definition.is_filterable:
                values.append(
                    {
                        "name": definition.name,
                        "slug": definition.slug,
                        "type": definition.value_type,
                        "value": attribute_public_value(attribute),
                    }
                )
        return sorted(values, key=lambda item: item["slug"])

    @extend_schema_field(serializers.IntegerField())
    def get_available_stock(self, variant):
        return variant_available_stock(variant)

    @extend_schema_field(serializers.BooleanField())
    def get_is_available(self, variant):
        return variant.stock_is_infinite or variant_available_stock(variant) > 0

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_purchase_limit(self, variant):
        return purchase_quantity_limit(variant)

    @extend_schema_field(PublicPricingSerializer)
    def get_pricing(self, variant):
        pricing = variant_pricing(variant)
        return {
            **pricing,
            "list_price": f"{pricing['list_price']:.2f}",
            "effective_price": f"{pricing['effective_price']:.2f}",
            "discount_amount": f"{pricing['discount_amount']:.2f}",
            "discount_percentage": f"{pricing['discount_percentage']:.2f}",
        }


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True, allow_null=True)
    variants = serializers.SerializerMethodField()
    media = ProductMediaSerializer(many=True, read_only=True)
    available_stock = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    on_offer = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "brand",
            "available_stock",
            "is_available",
            "effective_price",
            "on_offer",
            "variants",
            "media",
        )

    def _variants(self, product):
        prefetched = getattr(product, "_prefetched_objects_cache", {}).get("variants")
        variants = prefetched if prefetched is not None else product.variants.all()
        return [variant for variant in variants if variant.is_active]

    @extend_schema_field(PublicVariantSerializer(many=True))
    def get_variants(self, product):
        return PublicVariantSerializer(self._variants(product), many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_available_stock(self, product):
        return sum(max(variant_available_stock(variant), 0) for variant in self._variants(product))

    @extend_schema_field(serializers.BooleanField())
    def get_is_available(self, product):
        return any(
            variant.stock_is_infinite or variant_available_stock(variant) > 0
            for variant in self._variants(product)
        )

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True))
    def get_effective_price(self, product):
        prices = [
            variant_pricing(variant)["effective_price"]
            for variant in self._variants(product)
        ]
        return f"{min(prices):.2f}" if prices else None

    @extend_schema_field(serializers.BooleanField())
    def get_on_offer(self, product):
        return any(variant_pricing(variant)["on_offer"] for variant in self._variants(product))


class CatalogBrandFacetSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    count = serializers.IntegerField()


class CatalogCategoryFacetSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    count = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField())


class CatalogPriceFacetSerializer(serializers.Serializer):
    min = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    max = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class CatalogCountFacetSerializer(serializers.Serializer):
    in_stock = serializers.IntegerField(required=False)
    out_of_stock = serializers.IntegerField(required=False)
    on_offer = serializers.IntegerField(required=False)
    regular = serializers.IntegerField(required=False)


class CatalogAttributeValueFacetSerializer(serializers.Serializer):
    value = serializers.JSONField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class CatalogAttributeFacetSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    type = serializers.CharField()
    values = CatalogAttributeValueFacetSerializer(many=True)


class CatalogFacetsSerializer(serializers.Serializer):
    categories = CatalogCategoryFacetSerializer(many=True)
    brands = CatalogBrandFacetSerializer(many=True)
    price = CatalogPriceFacetSerializer()
    availability = CatalogCountFacetSerializer()
    offer = CatalogCountFacetSerializer()
    attributes = CatalogAttributeFacetSerializer(many=True)


class CatalogResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ProductSerializer(many=True)
    facets = CatalogFacetsSerializer()


class CatalogQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True)
    category = serializers.SlugField(required=False)
    brand = serializers.CharField(required=False)
    min_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    max_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    availability = serializers.ChoiceField(
        choices=("in_stock", "out_of_stock"), required=False
    )
    offer = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(
        choices=("relevance", "newest", "price_asc", "price_desc", "discount_desc"),
        default="relevance",
        required=False,
    )
    page = serializers.IntegerField(min_value=1, default=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=24, required=False)

    def validate(self, attrs):
        if (
            attrs.get("min_price") is not None
            and attrs.get("max_price") is not None
            and attrs["min_price"] > attrs["max_price"]
        ):
            raise serializers.ValidationError({"max_price": "Must be at least min_price"})
        attrs["query"] = (attrs.get("q") or attrs.get("search") or "").strip()
        return attrs
