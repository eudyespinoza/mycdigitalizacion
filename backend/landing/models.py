import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    URLValidator,
)
from django.db import models, transaction
from django.utils import timezone

from config.media import (
    delete_image_assets,
    generate_image_derivatives,
    safe_image_upload_to,
    validate_image_upload,
)

validate_https_url = URLValidator(schemes=("https",))
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
THEME_COLOR_FIELDS = (
    "theme_structure",
    "theme_action",
    "theme_wayfinding",
    "theme_background",
    "theme_text",
)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def theme_contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def validate_theme_configuration(values: dict[str, str]) -> None:
    errors = {}
    for field_name in THEME_COLOR_FIELDS:
        if not HEX_COLOR_PATTERN.fullmatch(values.get(field_name, "")):
            errors[field_name] = (
                "Ingresá un color hexadecimal de seis dígitos, por ejemplo #020530."
            )
    if errors:
        raise ValidationError(errors)
    background = values["theme_background"]
    contrast_pairs = (
        ("theme_text", background, "El texto necesita más contraste con el fondo."),
        (
            "theme_structure",
            background,
            "El color de estructura necesita más contraste con el fondo.",
        ),
        (
            "theme_wayfinding",
            background,
            "El color de orientación necesita más contraste con el fondo.",
        ),
        ("theme_action", "#FFFFFF", "El color de acción necesita más contraste con texto blanco."),
    )
    for field_name, comparison, message in contrast_pairs:
        if theme_contrast(values[field_name], comparison) < 4.5:
            errors[field_name] = message
    if errors:
        raise ValidationError(errors)


def normalize_whatsapp_number(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class SiteSettings(models.Model):
    class ThemePalette(models.TextChoices):
        PULSO = "pulso", "Pulso Comercial"
        OCEAN = "ocean", "Océano"
        CREATIVE = "creative", "Creativa"
        NATURAL = "natural", "Natural"
        CUSTOM = "custom", "Personalizada"

    public_name = models.CharField(max_length=120, default="mycdigitalizacion")
    announcement = models.CharField(max_length=240, blank=True)
    contact_email = models.EmailField(blank=True)
    pickup_enabled = models.BooleanField(default=True)
    pickup_label = models.CharField(max_length=120, default="Retiro en tienda")
    pickup_address = models.CharField(max_length=240, blank=True)
    pickup_hours = models.CharField(max_length=240, blank=True)
    instagram_url = models.URLField(blank=True, validators=[validate_https_url])
    facebook_url = models.URLField(blank=True, validators=[validate_https_url])
    tiktok_url = models.URLField(blank=True, validators=[validate_https_url])
    youtube_url = models.URLField(blank=True, validators=[validate_https_url])
    linkedin_url = models.URLField(blank=True, validators=[validate_https_url])
    whatsapp_enabled = models.BooleanField(default=False)
    whatsapp_number = models.CharField(max_length=32, blank=True)
    whatsapp_message = models.CharField(max_length=240, blank=True)
    theme_palette = models.CharField(
        max_length=16,
        choices=ThemePalette.choices,
        default=ThemePalette.PULSO,
    )
    theme_structure = models.CharField(max_length=7, default="#020530")
    theme_action = models.CharField(max_length=7, default="#BD1D59")
    theme_wayfinding = models.CharField(max_length=7, default="#007F96")
    theme_background = models.CharField(max_length=7, default="#FFFFFF")
    theme_text = models.CharField(max_length=7, default="#020530")
    logo = models.ImageField(
        upload_to=safe_image_upload_to("branding/logo"),
        blank=True,
        validators=[validate_image_upload],
    )
    logo_derivatives = models.JSONField(default=dict, blank=True, editable=False)
    favicon = models.ImageField(
        upload_to=safe_image_upload_to("branding/favicon"),
        blank=True,
        validators=[validate_image_upload],
    )

    def clean(self):
        super().clean()
        self.whatsapp_number = normalize_whatsapp_number(self.whatsapp_number)
        if self.whatsapp_enabled and not 8 <= len(self.whatsapp_number) <= 15:
            raise ValidationError(
                {"whatsapp_number": "Ingresá un número internacional de 8 a 15 dígitos."}
            )
        validate_theme_configuration(
            {field_name: getattr(self, field_name) for field_name in THEME_COLOR_FIELDS}
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        previous = SiteSettings.objects.filter(pk=1).values(
            "logo", "logo_derivatives", "favicon"
        ).first() or {}
        self.full_clean(exclude={"id"})
        new_assets = []
        superseded_assets = []
        try:
            with transaction.atomic():
                result = super().save(*args, **kwargs)
                changes = {}
                for field_name in ("logo", "favicon"):
                    field = getattr(self, field_name)
                    old_name = previous.get(field_name, "")
                    if old_name == field.name:
                        continue
                    new_asset = {
                        "storage": field.storage,
                        "source_name": field.name,
                        "derivatives": {},
                    }
                    if field.name:
                        new_assets.append(new_asset)
                    if old_name:
                        superseded_assets.append(
                            {
                                "storage": field.storage,
                                "source_name": old_name,
                                "derivatives": (
                                    previous.get("logo_derivatives", {})
                                    if field_name == "logo"
                                    else {}
                                ),
                            }
                        )
                logo_changed = previous.get("logo", "") != self.logo.name
                if self.logo and (logo_changed or not self.logo_derivatives):
                    derivatives = generate_image_derivatives(
                        storage=self.logo.storage,
                        name=self.logo.name,
                    )
                    self.logo_derivatives = derivatives
                    changes["logo_derivatives"] = derivatives
                    for asset in new_assets:
                        if asset["source_name"] == self.logo.name:
                            asset["derivatives"] = derivatives
                elif not self.logo and self.logo_derivatives:
                    self.logo_derivatives = {}
                    changes["logo_derivatives"] = {}
                if changes:
                    SiteSettings.objects.filter(pk=1).update(**changes)
        except Exception:
            for assets in new_assets:
                delete_image_assets(**assets)
            raise
        for assets in superseded_assets:
            delete_image_assets(**assets)
        return result

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
        validators=[validate_image_upload],
    )
    mobile_image = models.ImageField(
        upload_to=safe_image_upload_to("landing/mobile"),
        blank=True,
        validators=[validate_image_upload],
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
        previous = {}
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "desktop_image",
                "mobile_image",
                "desktop_derivatives",
                "mobile_derivatives",
            ).first() or {}
        self.full_clean()
        new_assets = []
        superseded_assets = []
        try:
            with transaction.atomic():
                result = super().save(*args, **kwargs)
                derivative_updates = {}
                for field_name in ("desktop_image", "mobile_image"):
                    field = getattr(self, field_name)
                    derivatives_name = f"{field_name.replace('_image', '')}_derivatives"
                    old_name = previous.get(field_name, "")
                    old_derivatives = previous.get(derivatives_name, {})
                    changed = old_name != field.name
                    new_asset = None
                    if changed and field.name:
                        new_asset = {
                            "storage": field.storage,
                            "source_name": field.name,
                            "derivatives": {},
                        }
                        new_assets.append(new_asset)
                    if field and (changed or not getattr(self, derivatives_name)):
                        derivatives = generate_image_derivatives(
                            storage=field.storage, name=field.name
                        )
                        if new_asset is not None:
                            new_asset["derivatives"] = derivatives
                        derivative_updates[derivatives_name] = derivatives
                        setattr(self, derivatives_name, derivatives)
                    elif not field and getattr(self, derivatives_name):
                        derivative_updates[derivatives_name] = {}
                        setattr(self, derivatives_name, {})
                    if changed and old_name:
                        superseded_assets.append(
                            {
                                "storage": field.storage,
                                "source_name": old_name,
                                "derivatives": old_derivatives,
                            }
                        )
                if derivative_updates:
                    type(self).objects.filter(pk=self.pk).update(**derivative_updates)
        except Exception:
            for assets in new_assets:
                delete_image_assets(**assets)
            raise
        for assets in superseded_assets:
            delete_image_assets(**assets)
        return result

    def delete(self, *args, **kwargs):
        assets = [
            {
                "storage": field.storage,
                "source_name": field.name,
                "derivatives": getattr(self, derivatives_name),
            }
            for field, derivatives_name in (
                (self.desktop_image, "desktop_derivatives"),
                (self.mobile_image, "mobile_derivatives"),
            )
        ]
        result = super().delete(*args, **kwargs)
        for image_assets in assets:
            delete_image_assets(**image_assets)
        return result


class HeroSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    interval_ms = models.PositiveIntegerField(
        default=6000, validators=[MinValueValidator(1000), MaxValueValidator(30000)]
    )
    pause_on_reduced_motion = models.BooleanField(default=True)

    class Meta(ScheduledContent.Meta):
        indexes = [
            models.Index(
                fields=("enabled", "order", "starts_at", "ends_at"),
                name="land_hero_schedule_idx",
            )
        ]


class PromotionSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    interval_ms = models.PositiveIntegerField(
        default=6000, validators=[MinValueValidator(1000), MaxValueValidator(30000)]
    )
    pause_on_reduced_motion = models.BooleanField(default=True)

    class Meta(ScheduledContent.Meta):
        indexes = [
            models.Index(
                fields=("enabled", "order", "starts_at", "ends_at"),
                name="land_promo_schedule_idx",
            )
        ]


class CatalogSlide(ScheduledContent):
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    interval_ms = models.PositiveIntegerField(
        default=6000, validators=[MinValueValidator(1000), MaxValueValidator(30000)]
    )
    pause_on_reduced_motion = models.BooleanField(default=True)

    class Meta(ScheduledContent.Meta):
        indexes = [
            models.Index(
                fields=("enabled", "order", "starts_at", "ends_at"),
                name="land_catalog_sched_idx",
            )
        ]


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
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta(ScheduledContent.Meta):
        indexes = [
            models.Index(
                fields=("enabled", "order", "starts_at", "ends_at"),
                name="land_popup_schedule_idx",
            )
        ]
