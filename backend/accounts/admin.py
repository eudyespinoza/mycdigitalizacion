from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse

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
    actions = ("export_selected_csv", "export_selected_xlsx")

    def _export(self, request, queryset, export_format):
        from commerce.exports import export_billing_profiles

        payload = export_billing_profiles(
            queryset,
            actor=request.user,
            export_format=export_format,
            filters={key: request.GET.getlist(key) for key in request.GET},
        )
        content_type = (
            "text/csv"
            if export_format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="fiscal.{export_format}"'
        return response

    @admin.action(description="Exportar fiscal a CSV", permissions=("view",))
    def export_selected_csv(self, request, queryset):
        return self._export(request, queryset, "csv")

    @admin.action(description="Exportar fiscal a XLSX", permissions=("view",))
    def export_selected_xlsx(self, request, queryset):
        return self._export(request, queryset, "xlsx")


admin.site.register(Profile)
admin.site.register(EmailVerificationChallenge)
