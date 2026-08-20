from django.contrib import admin

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


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "is_active", "is_sellable")
    list_filter = ("is_active", "is_sellable", "category", "brand")
    search_fields = ("name", "slug", "variants__sku")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductVariantInline, ProductMediaInline)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "price", "cost", "on_hand", "is_active")
    list_filter = ("is_active", "product__category")
    search_fields = ("sku", "product__name")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Brand)
admin.site.register(AttributeDefinition)
admin.site.register(AttributeOption)
admin.site.register(AttributeValue)
