from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from config.media import generate_image_derivatives, safe_image_upload_to, validate_image_upload


class SiteSettings(models.Model):
    public_name = models.CharField(max_length=120, default="mycdigitalizacion")
    announcement = models.CharField(max_length=240, blank=True)
    contact_email = models.EmailField(blank=True)
    pickup_enabled = models.BooleanField(default=True)
    pickup_label = models.CharField(max_length=120, default="Retiro en tienda")
    pickup_address = models.CharField(max_length=240, blank=True)
    pickup_hours = models.CharField(max_length=240, blank=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Site settings cannot be deleted")


def validate_cta_url(value):
    if not value:
        return
    if value.startswith("/") and not value.startswith("//"):
        return
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("CTA URL must be relative or use http/https")


class ScheduledContent(models.Model):
    enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    desktop_image = models.ImageField(
        upload_to=safe_image_upload_to("landing/desktop"),
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg", "webp", "avif"]),
            validate_image_upload,
        ],
    )
    mobile_image = models.ImageField(
        upload_to=safe_image_upload_to("landing/mobile"),
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg", "webp", "avif"]),
            validate_image_upload,
        ],
    )
    desktop_derivatives = models.JSONField(default=dict, blank=True, editable=False)
    mobile_derivatives = models.JSONField(default=dict, blank=True, editable=False)
    alt_text = models.CharField(max_length=240, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=300, blank=True, validators=[validate_cta_url])
    focal_x = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    focal_y = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    safe_height_mobile = models.PositiveIntegerField(
        default=320, validators=[MinValueValidator(120), MaxValueValidator(1200)]
    )
    safe_height_tablet = models.PositiveIntegerField(
        default=420, validators=[MinValueValidator(120), MaxValueValidator(1200)]
    )
    safe_height_desktop = models.PositiveIntegerField(
        default=520, validators=[MinValueValidator(120), MaxValueValidator(1200)]
    )

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

    def clean(self):
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValidationError("Content start must precede its end")
        if (self.desktop_image or self.mobile_image) and not self.alt_text.strip():
            raise ValidationError({"alt_text": "Alt text is required when an image is present"})

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        derivative_updates = {}
        for field_name in ("desktop_image", "mobile_image"):
            field = getattr(self, field_name)
            derivatives_name = f"{field_name.replace('_image', '')}_derivatives"
            if field and not getattr(self, derivatives_name):
                derivatives = generate_image_derivatives(storage=field.storage, name=field.name)
                if derivatives:
                    derivative_updates[derivatives_name] = derivatives
                    setattr(self, derivatives_name, derivatives)
        if derivative_updates:
            type(self).objects.filter(pk=self.pk).update(**derivative_updates)
        return result


class HeroSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    interval_ms = models.PositiveIntegerField(
        default=6000, validators=[MinValueValidator(1000), MaxValueValidator(30000)]
    )
    pause_on_reduced_motion = models.BooleanField(default=True)


class PromotionSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    interval_ms = models.PositiveIntegerField(
        default=6000, validators=[MinValueValidator(1000), MaxValueValidator(30000)]
    )
    pause_on_reduced_motion = models.BooleanField(default=True)


class LandingCollection(ScheduledContent):
    title = models.CharField(max_length=160)
    product_ids = models.JSONField(default=list, blank=True)

    def clean(self):
        super().clean()
        if not isinstance(self.product_ids, list) or any(
            isinstance(product_id, bool)
            or not isinstance(product_id, int)
            or product_id < 1
            for product_id in self.product_ids
        ):
            raise ValidationError("Collection product IDs must be positive integers")
        if len(self.product_ids) != len(set(self.product_ids)):
            raise ValidationError("Collection product IDs must be unique")


class PromotionPopup(ScheduledContent):
    class Frequency(models.TextChoices):
        ONCE_PER_SESSION = "once_session", "Once per session"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        ALWAYS = "always", "Always"

    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    frequency = models.CharField(
        max_length=20, choices=Frequency.choices, default=Frequency.ONCE_PER_SESSION
    )
    display_delay_ms = models.PositiveIntegerField(
        default=1500, validators=[MaxValueValidator(60000)]
    )
    dismissible = models.BooleanField(default=True)
