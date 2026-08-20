from django.contrib import admin

from locations.models import Address, PostalLocality


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "locality", "province", "postal_code", "needs_review")
    list_filter = ("province", "needs_review", "geocode_source")
    search_fields = ("user__email", "raw_address", "normalized_address", "postal_code", "cpa")


@admin.register(PostalLocality)
class PostalLocalityAdmin(admin.ModelAdmin):
    list_display = ("postal_code", "cpa", "locality", "province", "synced_at")
    search_fields = ("postal_code", "cpa", "locality", "province")
