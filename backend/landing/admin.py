import json

from django.contrib import admin
from django.contrib.messages.api import MessageFailure
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
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
    actions = ("duplicate_selected",)
    readonly_fields = ("thumbnail", "public_preview", "desktop_derivatives", "mobile_derivatives")
    change_list_template = "admin/landing/scheduledcontent/change_list.html"

    class Media:
        js = ("admin/js/mycd-sortable.js",)

    def get_urls(self):
        info = (self.opts.app_label, self.opts.model_name)
        return [
            path(
                "reorder/",
                self.admin_site.admin_view(self.reorder_view),
                name="{}_{}_reorder".format(*info),
            ),
            path(
                "<path:object_id>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="{}_{}_preview".format(*info),
            ),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        info = (self.opts.app_label, self.opts.model_name)
        context = {
            **(extra_context or {}),
            "mycd_reorder_url": reverse("admin:{}_{}_reorder".format(*info)),
        }
        return super().changelist_view(request, extra_context=context)

    def reorder_view(self, request):
        if request.method != "POST" or not self.has_change_permission(request):
            raise PermissionDenied
        try:
            payload = json.loads(request.body)
            item_id = int(payload["item_id"])
            target_id = int(payload["target_id"])
            position = payload["position"]
            if position not in {"before", "after"} or item_id == target_id:
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"code": "invalid_reorder"}, status=400)
        with transaction.atomic():
            objects = list(self.model.objects.select_for_update().order_by("order", "pk"))
            by_id = {obj.pk: obj for obj in objects}
            if item_id not in by_id or target_id not in by_id:
                return JsonResponse({"code": "content_not_found"}, status=404)
            item = by_id[item_id]
            target = by_id[target_id]
            objects.remove(item)
            target_index = objects.index(target) + (position == "after")
            objects.insert(target_index, item)
            changed = []
            for index, obj in enumerate(objects):
                if obj.order != index:
                    obj.order = index
                    changed.append(obj)
            self.model.objects.bulk_update(changed, ("order",))
        return JsonResponse({"status": "ok", "item_id": item_id, "order": item.order})

    def preview_view(self, request, object_id):
        obj = get_object_or_404(self.model, pk=object_id)
        if not self.has_view_permission(request, obj):
            raise PermissionDenied
        return TemplateResponse(
            request,
            "admin/landing/scheduledcontent/preview.html",
            {**self.admin_site.each_context(request), "content_object": obj},
        )

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
        info = (self.opts.app_label, self.opts.model_name)
        url = reverse("admin:{}_{}_preview".format(*info), args=(obj.pk,))
        return format_html('<a href="{}" target="_blank" rel="noopener">Vista previa</a>', url)

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
