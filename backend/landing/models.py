from django.db import models
from django.utils import timezone


class SiteSettings(models.Model):
    public_name = models.CharField(max_length=120, default="mycdigitalizacion")
    announcement = models.CharField(max_length=240, blank=True)
    contact_email = models.EmailField(blank=True)


class ScheduledContent(models.Model):
    enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    desktop_image = models.FileField(upload_to="landing/desktop", blank=True)
    mobile_image = models.FileField(upload_to="landing/mobile", blank=True)
    alt_text = models.CharField(max_length=240)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=300, blank=True)
    focal_x = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    focal_y = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    safe_height_mobile = models.PositiveIntegerField(default=320)
    safe_height_tablet = models.PositiveIntegerField(default=420)
    safe_height_desktop = models.PositiveIntegerField(default=520)

    class Meta:
        abstract = True
        ordering = ("order", "id")

    def is_scheduled(self, at=None):
        checked_at = at or timezone.now()
        return (
            self.enabled
            and (self.starts_at is None or self.starts_at <= checked_at)
            and (self.ends_at is None or self.ends_at >= checked_at)
        )


class HeroSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)


class PromotionSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)


class LandingCollection(ScheduledContent):
    title = models.CharField(max_length=160)
    product_ids = models.JSONField(default=list, blank=True)


class PromotionPopup(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
