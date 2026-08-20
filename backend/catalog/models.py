from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)

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


class Product(models.Model):
    category = models.ForeignKey(Category, related_name="products", on_delete=models.PROTECT)
    brand = models.ForeignKey(
        Brand, null=True, blank=True, related_name="products", on_delete=models.PROTECT
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_sellable = models.BooleanField(default=False)

    def clean(self):
        if self.is_sellable and (not self.pk or not self.variants.exists()):
            raise ValidationError("A sellable product requires at least one variant")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductMedia(models.Model):
    product = models.ForeignKey(Product, related_name="media", on_delete=models.CASCADE)
    file = models.FileField(upload_to="catalog")
    alt_text = models.CharField(max_length=240)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    packaged_weight_grams = models.PositiveIntegerField()
    length_cm = models.DecimalField(max_digits=9, decimal_places=2)
    width_cm = models.DecimalField(max_digits=9, decimal_places=2)
    height_cm = models.DecimalField(max_digits=9, decimal_places=2)
    is_active = models.BooleanField(default=True)
    on_hand = models.PositiveIntegerField(default=0)

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("variant", "definition"), name="unique_variant_attribute"
            )
        ]
