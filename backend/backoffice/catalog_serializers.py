from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import (
    AttributeDefinition,
    AttributeOption,
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductMedia,
    ProductVariant,
)
from catalog.serializers import variant_available_stock
from catalog.services import activate_product, move_category, set_variant_active
from commerce.inventory import adjust_inventory
from commerce.models import InventoryMovement, PromotionRule
from config.media import public_derivative_sources


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


class ManagementAttributeOptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = AttributeOption
        fields = ("id", "label", "value")


class ManagementAttributeDefinitionSerializer(serializers.ModelSerializer):
    options = ManagementAttributeOptionSerializer(many=True, required=False)

    class Meta:
        model = AttributeDefinition
        fields = ("id", "name", "slug", "value_type", "is_filterable", "options")

    def validate_options(self, options):
        values = [option["value"] for option in options]
        if len(values) != len(set(values)):
            raise serializers.ValidationError("Las opciones no pueden repetirse.")
        return options

    def _sync_options(self, definition, options):
        definition.options.all().delete()
        AttributeOption.objects.bulk_create(
            [
                AttributeOption(
                    definition=definition,
                    **{key: value for key, value in option.items() if key != "id"},
                )
                for option in options
            ]
        )

    @transaction.atomic
    def create(self, validated_data):
        options = validated_data.pop("options", [])
        definition = AttributeDefinition.objects.create(**validated_data)
        self._sync_options(definition, options)
        return definition

    @transaction.atomic
    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.full_clean()
        instance.save()
        if options is not None:
            self._sync_options(instance, options)
        return instance


class ManagementProductMediaSerializer(serializers.ModelSerializer):
    file = serializers.ImageField(write_only=True)
    file_url = serializers.SerializerMethodField()
    responsive_sources = serializers.SerializerMethodField()
    variant_id = serializers.PrimaryKeyRelatedField(
        source="variant",
        queryset=ProductVariant.objects.all(),
        allow_null=True,
        required=False,
    )
    variant_name = serializers.CharField(source="variant.name", read_only=True, default="")

    class Meta:
        model = ProductMedia
        fields = (
            "id",
            "file",
            "file_url",
            "responsive_sources",
            "variant_id",
            "variant_name",
            "alt_text",
            "order",
        )
        read_only_fields = ("id", "file_url", "responsive_sources")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        product = self.context.get("product") or getattr(self.instance, "product", None)
        variant = attrs.get("variant", getattr(self.instance, "variant", None))
        if product and variant and variant.product_id != product.pk:
            raise serializers.ValidationError(
                {"variant_id": "La variante debe pertenecer al mismo producto."}
            )
        return attrs

    @extend_schema_field(serializers.CharField())
    def get_file_url(self, instance):
        return instance.file.url if instance.file else ""

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_responsive_sources(self, instance):
        return public_derivative_sources(
            storage=instance.file.storage,
            derivatives=instance.derivatives,
        )


class InventoryMovementSummarySerializer(serializers.ModelSerializer):
    actor = serializers.EmailField(source="actor.email", allow_null=True)

    class Meta:
        model = InventoryMovement
        fields = ("id", "kind", "quantity_delta", "reference", "source", "actor", "created_at")


class ManagementVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    available_stock = serializers.SerializerMethodField()
    on_hand = serializers.IntegerField(min_value=0)
    recent_movements = serializers.SerializerMethodField(read_only=True)
    attributes = serializers.SerializerMethodField(read_only=True)
    attribute_values = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
    )

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
            "stock_is_infinite",
            "max_purchase_quantity",
            "is_active",
            "packaged_weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
            "recent_movements",
            "attributes",
            "attribute_values",
        )
        read_only_fields = ("available_stock", "recent_movements", "attributes")
        extra_kwargs = {"sku": {"validators": []}}

    def validate_attribute_values(self, values):
        normalized = []
        seen = set()
        for item in values:
            definition_id = item.get("definition_id")
            if not definition_id or "value" not in item:
                raise serializers.ValidationError("Cada atributo necesita definición y valor.")
            if definition_id in seen:
                raise serializers.ValidationError("No repitas el mismo atributo.")
            seen.add(definition_id)
            try:
                definition = AttributeDefinition.objects.get(pk=definition_id)
            except AttributeDefinition.DoesNotExist as exc:
                raise serializers.ValidationError("El atributo seleccionado no existe.") from exc
            value = item["value"]
            try:
                if definition.value_type == AttributeDefinition.ValueType.INTEGER:
                    value = int(value)
                elif definition.value_type == AttributeDefinition.ValueType.DECIMAL:
                    value = str(value)
                elif definition.value_type == AttributeDefinition.ValueType.BOOLEAN:
                    if not isinstance(value, bool):
                        raise ValueError
                elif definition.value_type == AttributeDefinition.ValueType.OPTION:
                    AttributeOption.objects.get(definition=definition, value=str(value))
                else:
                    value = str(value).strip()
                    if not value:
                        raise ValueError
            except (AttributeOption.DoesNotExist, TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    f"El valor de {definition.name} no es válido."
                ) from exc
            normalized.append({"definition": definition, "value": value})
        return normalized

    @extend_schema_field(InventoryMovementSummarySerializer(many=True))
    def get_recent_movements(self, variant):
        movements = getattr(variant, "management_recent_movements", None)
        if movements is None:
            movements = variant.inventory_movements.select_related("actor").order_by(
                "-created_at"
            )[:5]
        return InventoryMovementSummarySerializer(movements, many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_available_stock(self, variant):
        return variant_available_stock(variant)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attributes(self, variant):
        values = []
        prefetched = getattr(variant, "_prefetched_objects_cache", {}).get("attribute_values")
        attributes = (
            prefetched
            if prefetched is not None
            else variant.attribute_values.select_related("definition", "option")
        )
        for attribute in attributes:
            definition = attribute.definition
            if definition.value_type == AttributeDefinition.ValueType.OPTION:
                value = attribute.option.value
            else:
                value = getattr(attribute, f"{definition.value_type}_value")
            values.append(
                {
                    "definition_id": definition.pk,
                    "name": definition.name,
                    "slug": definition.slug,
                    "value_type": definition.value_type,
                    "value": value,
                }
            )
        return values


class ManagementVariantSummarySerializer(serializers.ModelSerializer):
    available_stock = serializers.SerializerMethodField()

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
            "stock_is_infinite",
            "max_purchase_quantity",
            "is_active",
            "packaged_weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_available_stock(self, variant):
        return variant_available_stock(variant)


def active_offer_names(product):
    product_rules = getattr(product, "active_management_promotions", None)
    category_rules = getattr(product.category, "active_management_promotions", None)
    if product_rules is not None and category_rules is not None:
        return sorted({rule.name for rule in (*product_rules, *category_rules)})
    checked_at = timezone.now()
    return list(
        PromotionRule.objects.filter(
            enabled=True,
            starts_at__lte=checked_at,
            ends_at__gte=checked_at,
        )
        .filter(Q(products=product) | Q(categories=product.category))
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )


class ManagementOfferStateMixin(serializers.Serializer):
    on_offer = serializers.SerializerMethodField()
    active_offer_names = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_on_offer(self, product):
        return bool(active_offer_names(product))

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_active_offer_names(self, product):
        return active_offer_names(product)


class ManagementProductSummarySerializer(
    ManagementOfferStateMixin,
    serializers.ModelSerializer,
):
    category = ManagementCategorySerializer(read_only=True)
    brand = ManagementBrandSerializer(read_only=True)
    variants = ManagementVariantSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "brand",
            "is_active",
            "is_sellable",
            "created_at",
            "on_offer",
            "active_offer_names",
            "variants",
        )


class ManagementProductSerializer(ManagementOfferStateMixin, serializers.ModelSerializer):
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
    media = ManagementProductMediaSerializer(many=True, read_only=True)
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
            "on_offer",
            "active_offer_names",
            "variants",
            "media",
            "publish",
        )
        read_only_fields = ("id", "is_active", "is_sellable", "created_at")

    def validate_variants(self, variants):
        if not variants and not self.instance:
            raise serializers.ValidationError("Cargá al menos una variante.")
        errors = [{} for _ in variants]
        skus = [variant["sku"] for variant in variants]
        variant_ids = [variant.get("id") for variant in variants if variant.get("id")]
        allowed_ids = (
            set(self.instance.variants.filter(pk__in=variant_ids).values_list("pk", flat=True))
            if self.instance
            else set()
        )
        existing_by_sku = {
            sku: pk
            for pk, sku in ProductVariant.objects.filter(sku__in=skus).values_list("pk", "sku")
        }
        seen_skus = set()
        seen_ids = set()
        for index, variant in enumerate(variants):
            sku = variant["sku"]
            variant_id = variant.get("id")
            if sku in seen_skus:
                errors[index]["sku"] = ["El SKU está repetido en este producto."]
            seen_skus.add(sku)
            if variant_id:
                if variant_id in seen_ids:
                    errors[index]["id"] = ["La variante está repetida en el formulario."]
                elif variant_id not in allowed_ids:
                    errors[index]["id"] = ["La variante no pertenece a este producto."]
                seen_ids.add(variant_id)
            existing_id = existing_by_sku.get(sku)
            if existing_id and existing_id != variant_id:
                errors[index]["sku"] = ["Ya existe otra variante con este SKU."]
        if any(errors):
            raise serializers.ValidationError(errors)
        return variants

    def _save_variant(self, *, product, values, actor):
        attribute_values = values.pop("attribute_values", None)
        initial_stock = values.pop("on_hand", None)
        variant_id = values.pop("id", None)
        if variant_id:
            variant = ProductVariant.objects.select_for_update().get(
                product=product,
                pk=variant_id,
            )
            active = values.pop("is_active", variant.is_active)
            changed_fields = []
            for field, value in values.items():
                if getattr(variant, field) != value:
                    setattr(variant, field, value)
                    changed_fields.append(field)
            if changed_fields:
                variant.save(update_fields=changed_fields)
            if active != variant.is_active:
                variant = set_variant_active(variant=variant, active=active)
        else:
            variant = ProductVariant.objects.create(product=product, on_hand=0, **values)
        if variant_id is None and initial_stock is not None and initial_stock != variant.on_hand:
            variant = adjust_inventory(
                variant=variant,
                new_on_hand=initial_stock,
                actor=actor,
                source="domain",
                reference=f"Carga de producto: {variant.sku}",
            )
        if attribute_values is not None:
            self._sync_attribute_values(variant, attribute_values)
        return variant

    def _sync_attribute_values(self, variant, values):
        variant.attribute_values.all().delete()
        for item in values:
            definition = item["definition"]
            value = item["value"]
            fields = {
                "text_value": "",
                "integer_value": None,
                "decimal_value": None,
                "boolean_value": None,
                "option": None,
            }
            if definition.value_type == AttributeDefinition.ValueType.OPTION:
                fields["option"] = AttributeOption.objects.get(
                    definition=definition,
                    value=str(value),
                )
            else:
                fields[f"{definition.value_type}_value"] = value
            AttributeValue.objects.create(
                variant=variant,
                definition=definition,
                **fields,
            )

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
                instance._prefetched_objects_cache.pop("variants", None)
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
