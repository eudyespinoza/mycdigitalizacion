from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Now
from django.utils import timezone

from config.media import (
    delete_image_assets,
    generate_image_derivatives,
    safe_image_upload_to,
    validate_image_upload,
)


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class CategoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "parent" in kwargs or "parent_id" in kwargs:
            raise ValidationError("Use move_category to change category ancestry")
        return super().update(**kwargs)


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)
    objects = CategoryQuerySet.as_manager()

    def clean(self):
        depth = 1
        ancestor = self.parent
        seen = {self.pk} if self.pk else set()
        while ancestor:
            if ancestor.pk in seen:
                raise ValidationError("Category cannot contain a cycle")
            seen.add(ancestor.pk)
            depth += 1
            if depth > 5:
                raise ValidationError("Category trees are limited to five levels")
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_allow_reparent", False):
            original_parent_id = type(self)._base_manager.filter(pk=self.pk).values_list(
                "parent_id", flat=True
            ).first()
            if original_parent_id != self.parent_id:
                raise ValidationError("Use move_category to change category ancestry")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AttributeDefinition(models.Model):
    class ValueType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        OPTION = "option", "Option"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    value_type = models.CharField(max_length=16, choices=ValueType.choices)
    is_filterable = models.BooleanField(default=True)


class AttributeOption(models.Model):
    definition = models.ForeignKey(
        AttributeDefinition, related_name="options", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=120)
    value = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("definition", "value"), name="unique_attribute_option_value"
            )
        ]


class ProductQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "is_active" in kwargs or "is_sellable" in kwargs:
            raise ValidationError("Use the product activation service")
        return super().update(**kwargs)


class Product(models.Model):
    category = models.ForeignKey(Category, related_name="products", on_delete=models.PROTECT)
    brand = models.ForeignKey(
        Brand, null=True, blank=True, related_name="products", on_delete=models.PROTECT
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=Now(), editable=False)
    is_active = models.BooleanField(default=True)
    is_sellable = models.BooleanField(default=False)
    objects = ProductQuerySet.as_manager()

    class Meta:
        permissions = (
            ("import_product", "Can import products with validation"),
            ("export_product", "Can export product administration data"),
        )

    def clean(self):
        if self.is_sellable and (
            not self.pk or not self.variants.filter(is_active=True).exists()
        ):
            raise ValidationError("A sellable product requires at least one active variant")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not getattr(self, "_allow_activation", False):
            original = type(self)._base_manager.filter(pk=self.pk).values(
                "is_active", "is_sellable"
            ).get()
            activating = (
                (not original["is_active"] and self.is_active)
                or (not original["is_sellable"] and self.is_sellable)
            )
            if activating:
                raise ValidationError("Use the product activation service")
        return super().save(*args, **kwargs)

    def _save_activation(self):
        self._allow_activation = True
        try:
            self.save(update_fields=["is_active", "is_sellable"])
        finally:
            del self._allow_activation

    def __str__(self):
        return self.name


class ProductMedia(models.Model):
    product = models.ForeignKey(Product, related_name="media", on_delete=models.CASCADE)
    file = models.ImageField(
        upload_to=safe_image_upload_to("catalog"), validators=[validate_image_upload]
    )
    alt_text = models.CharField(max_length=240)
    order = models.PositiveIntegerField(default=0)
    derivatives = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        ordering = ("order", "id")

    def clean(self):
        if self.file and not self.alt_text.strip():
            raise ValidationError({"alt_text": "Alt text is required when an image is present"})

    def save(self, *args, **kwargs):
        previous = (
            type(self).objects.filter(pk=self.pk).values("file", "derivatives").first()
            if self.pk
            else None
        ) or {}
        self.full_clean()
        result = super().save(*args, **kwargs)
        old_name = previous.get("file", "")
        old_derivatives = previous.get("derivatives", {})
        changed = old_name != self.file.name
        if self.file and (changed or not self.derivatives):
            derivatives = generate_image_derivatives(
                storage=self.file.storage, name=self.file.name
            )
            type(self).objects.filter(pk=self.pk).update(derivatives=derivatives)
            self.derivatives = derivatives
        if changed and old_name:
            delete_image_assets(
                storage=self.file.storage,
                source_name=old_name,
                derivatives=old_derivatives,
            )
        return result


class ProductVariantQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs.get("is_active") is False:
            active_sellable = self.filter(is_active=True, product__is_sellable=True)
            for product_id in active_sellable.values_list("product_id", flat=True).distinct():
                deactivating = active_sellable.filter(product_id=product_id).count()
                active = ProductVariant.objects.filter(
                    product_id=product_id, is_active=True
                ).count()
                if deactivating >= active:
                    raise ValidationError("Cannot deactivate the last active variant")
        return super().update(**kwargs)

    def delete(self):
        active_sellable = self.filter(is_active=True, product__is_sellable=True)
        for product_id in active_sellable.values_list("product_id", flat=True).distinct():
            deleting = active_sellable.filter(product_id=product_id).count()
            remaining = ProductVariant.objects.filter(
                product_id=product_id, is_active=True
            ).count()
            if deleting >= remaining:
                raise ValidationError("Cannot delete the last active variant")
        return super().delete()


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120, blank=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    packaged_weight_grams = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    length_cm = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    width_cm = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    height_cm = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)
    on_hand = models.PositiveIntegerField(default=0)
    objects = ProductVariantQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="variant_price_nonnegative"),
            models.CheckConstraint(condition=Q(cost__gte=0), name="variant_cost_nonnegative"),
            models.CheckConstraint(
                condition=Q(packaged_weight_grams__gt=0), name="variant_weight_positive"
            ),
            models.CheckConstraint(condition=Q(length_cm__gt=0), name="variant_length_positive"),
            models.CheckConstraint(condition=Q(width_cm__gt=0), name="variant_width_positive"),
            models.CheckConstraint(condition=Q(height_cm__gt=0), name="variant_height_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_allow_state_change", False):
            original = type(self)._base_manager.filter(pk=self.pk).values("is_active").first()
            if (
                original
                and original["is_active"]
                and not self.is_active
                and self.product.is_sellable
                and not self.product.variants.filter(is_active=True).exclude(pk=self.pk).exists()
            ):
                raise ValidationError("Cannot deactivate the last active variant")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if (
            not getattr(self, "_allow_delete", False)
            and self.is_active
            and self.product.is_sellable
            and not self.product.variants.filter(is_active=True).exclude(pk=self.pk).exists()
        ):
            raise ValidationError("Cannot delete the last active variant")
        return super().delete(*args, **kwargs)

    @property
    def volume_cm3(self):
        return (self.length_cm * self.width_cm * self.height_cm).quantize(
            Decimal("0.000001")
        )

    @property
    def available_stock(self):
        reserved = (
            self.stock_reservations.filter(
                status="active", expires_at__gt=timezone.now()
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        return self.on_hand - reserved

    def __str__(self):
        return self.sku


class AttributeValueQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use AttributeValue.save() or its write service")

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            obj.full_clean()
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        del batch_size
        with transaction.atomic():
            for obj in objs:
                obj.full_clean()
            for obj in objs:
                obj.save(update_fields=fields)
        return len(objs)


class AttributeValue(models.Model):
    variant = models.ForeignKey(
        ProductVariant, related_name="attribute_values", on_delete=models.CASCADE
    )
    definition = models.ForeignKey(AttributeDefinition, on_delete=models.PROTECT)
    option = models.ForeignKey(AttributeOption, null=True, blank=True, on_delete=models.PROTECT)
    text_value = models.TextField(blank=True)
    integer_value = models.IntegerField(null=True, blank=True)
    decimal_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    objects = AttributeValueQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("variant", "definition"), name="unique_variant_attribute"
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(text_value__gt="")
                        & Q(integer_value__isnull=True)
                        & Q(decimal_value__isnull=True)
                        & Q(boolean_value__isnull=True)
                        & Q(option__isnull=True)
                    )
                    | (
                        Q(text_value="")
                        & Q(integer_value__isnull=False)
                        & Q(decimal_value__isnull=True)
                        & Q(boolean_value__isnull=True)
                        & Q(option__isnull=True)
                    )
                    | (
                        Q(text_value="")
                        & Q(integer_value__isnull=True)
                        & Q(decimal_value__isnull=False)
                        & Q(boolean_value__isnull=True)
                        & Q(option__isnull=True)
                    )
                    | (
                        Q(text_value="")
                        & Q(integer_value__isnull=True)
                        & Q(decimal_value__isnull=True)
                        & Q(boolean_value__isnull=False)
                        & Q(option__isnull=True)
                    )
                    | (
                        Q(text_value="")
                        & Q(integer_value__isnull=True)
                        & Q(decimal_value__isnull=True)
                        & Q(boolean_value__isnull=True)
                        & Q(option__isnull=False)
                    )
                ),
                name="attribute_value_exactly_one_storage",
            ),
        ]

    def clean(self):
        expected_field = {
            "text": "text_value",
            "integer": "integer_value",
            "decimal": "decimal_value",
            "boolean": "boolean_value",
            "option": "option",
        }[self.definition.value_type]
        populated = {
            "text_value": self.text_value != "",
            "integer_value": self.integer_value is not None,
            "decimal_value": self.decimal_value is not None,
            "boolean_value": self.boolean_value is not None,
            "option": self.option_id is not None,
        }
        if sum(populated.values()) != 1 or not populated[expected_field]:
            raise ValidationError("Attribute value must use exactly its declared value type")
        if self.option_id and self.option.definition_id != self.definition_id:
            raise ValidationError("Attribute option must belong to the same definition")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
