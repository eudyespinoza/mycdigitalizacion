from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import (
    BillingProfile,
    CustomerProfile,
    EmailVerificationChallenge,
    Profile,
    User,
)


@admin.register(User)
class EmailUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "email_verified_at", "is_staff", "is_active")
    search_fields = ("email",)
    list_filter = ("is_staff", "is_active", "email_verified_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Status", {"fields": ("email_verified_at", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "password1", "password2")}),)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "masked_dni", "masked_cuit", "consent_version", "consented_at")
    search_fields = ("user__email", "dni_hash", "cuit_hash")
    readonly_fields = ("dni_encrypted", "dni_hash", "cuit_encrypted", "cuit_hash")


admin.site.register(Profile)
admin.site.register(BillingProfile)
admin.site.register(EmailVerificationChallenge)
