from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Brand, Category, Product, ProductVariant
from catalog.services import activate_product, move_category, set_variant_active
from commerce.inventory import adjust_inventory
from commerce.models import InventoryMovement


class ManagementCategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=Category.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent_id", "is_active")

    def update(self, instance, validated_data):
        parent_marker = object()
        parent = validated_data.pop("parent", parent_marker)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if parent is not parent_marker and parent != instance.parent:
            instance = move_category(category=instance, new_parent=parent)
        return instance


class ManagementBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug")


class InventoryMovementSummarySerializer(serializers.ModelSerializer):
    actor = serializers.EmailField(source="actor.email", allow_null=True)

    class Meta:
        model = InventoryMovement
        fields = ("id", "kind", "quantity_delta", "reference", "source", "actor", "created_at")


class ManagementVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    available_stock = serializers.IntegerField(read_only=True)
    on_hand = serializers.IntegerField(min_value=0)
    recent_movements = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "name",
            "price",
            "cost",
            "on_hand",
            "available_stock",
            "is_active",
            "packaged_weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
            "recent_movements",
        )
        read_only_fields = ("available_stock", "recent_movements")

    @extend_schema_field(InventoryMovementSummarySerializer(many=True))
    def get_recent_movements(self, variant):
        movements = variant.inventory_movements.select_related("actor").order_by("-created_at")[:5]
        return InventoryMovementSummarySerializer(movements, many=True).data


class ManagementProductSerializer(serializers.ModelSerializer):
    category = ManagementCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    brand = ManagementBrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        source="brand",
        queryset=Brand.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
    )
    variants = ManagementVariantSerializer(many=True)
    publish = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "category_id",
            "brand",
            "brand_id",
            "is_active",
            "is_sellable",
            "created_at",
            "variants",
            "publish",
        )
        read_only_fields = ("id", "is_active", "is_sellable", "created_at")

    def validate_variants(self, variants):
        if not variants and not self.instance:
            raise serializers.ValidationError("Cargá al menos una variante.")
        skus = [variant["sku"] for variant in variants]
        if len(skus) != len(set(skus)):
            raise serializers.ValidationError("Los SKU no pueden repetirse.")
        return variants

    def _save_variant(self, *, product, values, actor):
        initial_stock = values.pop("on_hand", 0)
        variant_id = values.pop("id", None)
        if variant_id:
            variant = product.variants.get(pk=variant_id)
            active = values.pop("is_active", variant.is_active)
            for field, value in values.items():
                setattr(variant, field, value)
            variant.save()
            if active != variant.is_active:
                variant = set_variant_active(variant=variant, active=active)
        else:
            variant = ProductVariant.objects.create(product=product, on_hand=0, **values)
        if initial_stock != variant.on_hand:
            variant = adjust_inventory(
                variant=variant,
                new_on_hand=initial_stock,
                actor=actor,
                source="domain",
                reference=f"Carga de producto: {variant.sku}",
            )
        return variant

    @transaction.atomic
    def create(self, validated_data):
        variants = validated_data.pop("variants")
        publish = validated_data.pop("publish", False)
        product = Product.objects.create(is_active=True, is_sellable=False, **validated_data)
        actor = self.context["request"].user
        for values in variants:
            self._save_variant(product=product, values=values, actor=actor)
        if publish:
            product = activate_product(product=product)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        variants = validated_data.pop("variants", None)
        publish = validated_data.pop("publish", instance.is_sellable)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.save()
            if variants is not None:
                actor = self.context["request"].user
                for values in variants:
                    self._save_variant(product=instance, values=values, actor=actor)
            if publish and not instance.is_sellable:
                instance = activate_product(product=instance)
            elif not publish and instance.is_sellable:
                instance.is_sellable = False
                instance.save(update_fields=("is_sellable",))
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise serializers.ValidationError(detail) from exc
        return instance


class StockAdjustmentSerializer(serializers.Serializer):
    new_on_hand = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=160, allow_blank=False, trim_whitespace=True)
