from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import (
    BillingProfile,
    CustomerProfile,
    EmailVerificationChallenge,
    Profile,
    User,
)


class CustomerProfileAdminForm(forms.ModelForm):
    replacement_dni = forms.CharField(required=False, widget=forms.PasswordInput)
    replacement_cuit = forms.CharField(required=False, widget=forms.PasswordInput)

    class Meta:
        model = CustomerProfile
        fields = ("user", "consent_version", "consented_at")

    def clean_replacement_dni(self):
        value = self.cleaned_data["replacement_dni"]
        if value:
            from accounts.models import normalize_dni

            normalize_dni(value)
        return value

    def clean_replacement_cuit(self):
        value = self.cleaned_data["replacement_cuit"]
        if value:
            from accounts.models import normalize_cuit

            normalize_cuit(value)
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("replacement_dni"):
            instance.set_dni(self.cleaned_data["replacement_dni"])
        if self.cleaned_data.get("replacement_cuit"):
            instance.set_cuit(self.cleaned_data["replacement_cuit"])
        if commit:
            instance.save()
        return instance


class BillingProfileAdminForm(forms.ModelForm):
    replacement_cuit = forms.CharField(required=False, widget=forms.PasswordInput)

    class Meta:
        model = BillingProfile
        fields = ("customer", "label", "legal_name", "tax_condition", "is_default")

    def clean_replacement_cuit(self):
        value = self.cleaned_data["replacement_cuit"]
        if value:
            from accounts.models import normalize_cuit

            normalize_cuit(value)
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("replacement_cuit"):
            instance.set_cuit(self.cleaned_data["replacement_cuit"])
        if commit:
            instance.save()
        return instance


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
    form = CustomerProfileAdminForm
    list_display = ("user", "masked_dni", "masked_cuit", "consent_version", "consented_at")
    search_fields = ("user__email", "dni_hash", "cuit_hash")
    readonly_fields = ("masked_dni", "masked_cuit")
    fields = (
        "user",
        "consent_version",
        "consented_at",
        "masked_dni",
        "masked_cuit",
        "replacement_dni",
        "replacement_cuit",
    )


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
    form = BillingProfileAdminForm
    list_display = ("customer", "label", "legal_name", "masked_cuit", "is_default")
    search_fields = ("customer__user__email", "legal_name", "cuit_hash")
    readonly_fields = ("masked_cuit",)
    fields = (
        "customer",
        "label",
        "legal_name",
        "tax_condition",
        "is_default",
        "masked_cuit",
        "replacement_cuit",
    )


admin.site.register(Profile)
admin.site.register(EmailVerificationChallenge)
