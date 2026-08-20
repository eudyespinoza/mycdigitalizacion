from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

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
    fields = (
        "sku",
        "name",
        "price",
        "cost",
        "on_hand",
        "packaged_weight_grams",
        "length_cm",
        "width_cm",
        "height_cm",
        "is_active",
    )
    readonly_fields = ("on_hand",)


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0
    fields = ("file", "alt_text", "order", "derivatives")
    readonly_fields = ("derivatives",)


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 0
    fields = (
        "definition",
        "option",
        "text_value",
        "integer_value",
        "decimal_value",
        "boolean_value",
    )


class InventoryAdjustmentForm(forms.Form):
    new_on_hand = forms.IntegerField(min_value=0, label="Stock físico resultante")
    reference = forms.CharField(max_length=160, label="Motivo / referencia")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "is_active", "is_sellable")
    list_filter = ("is_active", "is_sellable", "category", "brand")
    search_fields = ("name", "slug", "variants__sku")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductVariantInline, ProductMediaInline)
    actions = ("export_selected_csv",)

    def get_urls(self):
        return [
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv_view),
                name="catalog_product_import_csv",
            )
        ] + super().get_urls()

    def import_csv_view(self, request):
        from catalog.admin_io import import_products_csv

        if not request.user.has_perm("catalog.import_product"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        context = {**self.admin_site.each_context(request), "result": None}
        if request.method == "POST" and request.FILES.get("csv_file"):
            context["result"] = import_products_csv(
                request.FILES["csv_file"],
                dry_run=request.POST.get("commit") != "1",
                actor=request.user,
            )
        from django.template.response import TemplateResponse

        return TemplateResponse(request, "admin/catalog/product/import_csv.html", context)

    @admin.action(
        description="Exportar variantes seleccionadas a CSV", permissions=("export_product",)
    )
    def export_selected_csv(self, request, queryset):
        if not request.user.has_perm("catalog.export_product"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        from catalog.admin_io import export_products_csv

        variants = ProductVariant.objects.filter(product__in=queryset).select_related("product")
        response = HttpResponse(export_products_csv(variants), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="catalogo.csv"'
        return response

    def has_export_product_permission(self, request):
        return request.user.has_perm("catalog.export_product")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "product",
        "price",
        "cost",
        "on_hand",
        "available_stock",
        "stock_adjustment",
        "inventory_history",
        "is_active",
    )
    list_filter = ("is_active", "product__category")
    search_fields = ("sku", "product__name")
    inlines = (AttributeValueInline,)
    readonly_fields = ("on_hand",)

    def get_urls(self):
        info = (self.opts.app_label, self.opts.model_name)
        return [
            path(
                "<path:object_id>/adjust-stock/",
                self.admin_site.admin_view(self.adjust_stock_view),
                name="{}_{}_adjust_stock".format(*info),
            )
        ] + super().get_urls()

    def adjust_stock_view(self, request, object_id):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404, redirect
        from django.template.response import TemplateResponse

        from commerce.inventory import adjust_inventory

        variant = get_object_or_404(ProductVariant, pk=object_id)
        if not self.has_change_permission(request, variant):
            raise PermissionDenied
        form = InventoryAdjustmentForm(
            request.POST or None, initial={"new_on_hand": variant.on_hand}
        )
        if request.method == "POST" and form.is_valid():
            adjust_inventory(
                variant=variant,
                new_on_hand=form.cleaned_data["new_on_hand"],
                actor=request.user,
                source="admin",
                reference=form.cleaned_data["reference"],
            )
            messages.success(request, "Stock actualizado y movimiento auditado.")
            return redirect("admin:catalog_productvariant_change", object_id)
        return TemplateResponse(
            request,
            "admin/catalog/productvariant/adjust_stock.html",
            {**self.admin_site.each_context(request), "form": form, "variant": variant},
        )

    @admin.display(description="Ajuste")
    def stock_adjustment(self, obj):
        url = reverse("admin:catalog_productvariant_adjust_stock", args=(obj.pk,))
        return format_html('<a href="{}">Ajustar vía servicio</a>', url)

    @admin.display(description="Historial")
    def inventory_history(self, obj):
        url = reverse("admin:commerce_inventorymovement_changelist")
        return format_html('<a href="{}?variant__id__exact={}">Ver movimientos</a>', url, obj.pk)


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
