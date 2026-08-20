from django.contrib import admin

from locations.models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "locality", "province", "postal_code", "needs_review")
    list_filter = ("province", "needs_review", "geocode_source")
    search_fields = ("user__email", "raw_address", "normalized_address", "postal_code", "cpa")
