from django.contrib import admin

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
