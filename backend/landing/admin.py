from django.contrib import admin
from django.contrib.messages.api import MessageFailure
from django.utils.html import format_html

from landing.models import (
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
    SiteSettings,
)


class ScheduledContentAdmin(admin.ModelAdmin):
    list_display = ("title", "enabled", "order", "starts_at", "ends_at")
    list_filter = ("enabled",)
    search_fields = ("title", "alt_text", "cta_label")
    ordering = ("order",)
    list_editable = ("order",)
    actions = ("duplicate_selected",)
    readonly_fields = ("thumbnail", "public_preview", "desktop_derivatives", "mobile_derivatives")

    class Media:
        js = ("admin/js/mycd-sortable.js",)

    @admin.display(description="Miniatura")
    def thumbnail(self, obj):
        image = obj.desktop_image or obj.mobile_image
        if not image:
            return "Sin imagen"
        return format_html(
            '<img src="{}" alt="{}" width="160" height="90" '
            'style="object-fit:cover;object-position:{}% {}%">',
            image.url,
            obj.alt_text,
            obj.focal_x,
            obj.focal_y,
        )

    @admin.display(description="Vista pública")
    def public_preview(self, obj):
        return format_html('<a href="/" target="_blank" rel="noopener">Abrir portada</a>')

    @admin.action(description="Duplicar contenido seleccionado")
    def duplicate_selected(self, request, queryset):
        duplicated = 0
        for original in queryset.order_by("pk"):
            original.pk = None
            original.title = f"{original.title} (copia)"[:160]
            original.order += 1
            original.enabled = False
            original.save()
            duplicated += 1
        try:
            self.message_user(request, f"{duplicated} elemento(s) duplicado(s).")
        except MessageFailure:
            pass


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(HeroSlide, ScheduledContentAdmin)
admin.site.register(PromotionSlide, ScheduledContentAdmin)
admin.site.register(LandingCollection, ScheduledContentAdmin)
admin.site.register(PromotionPopup, ScheduledContentAdmin)
