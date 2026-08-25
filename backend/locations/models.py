from django.conf import settings
from django.db import models


class Address(models.Model):
    class GeocodeSource(models.TextChoices):
        NONE = "", "None"
        MANUAL = "manual", "Manual"
        GEOREF = "georef", "GeoRef"
        OPENSTREETMAP = "openstreetmap", "OpenStreetMap"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="addresses", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=120)
    raw_address = models.CharField(max_length=300)
    normalized_address = models.CharField(max_length=300, blank=True)
    street = models.CharField(max_length=160)
    number = models.CharField(max_length=32)
    postal_code = models.CharField(max_length=16)
    cpa = models.CharField(max_length=16, blank=True)
    locality = models.CharField(max_length=120)
    province = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    floor = models.CharField(max_length=32, blank=True)
    apartment = models.CharField(max_length=32, blank=True)
    reference = models.CharField(max_length=240, blank=True)
    notes = models.TextField(blank=True)
    geocode_source = models.CharField(
        max_length=24, choices=GeocodeSource.choices, default=GeocodeSource.NONE, blank=True
    )
    geocode_confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    geocode_summary = models.JSONField(default=dict, blank=True)
    needs_review = models.BooleanField(default=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PostalLocality(models.Model):
    provider_id = models.CharField(max_length=120, unique=True)
    postal_code = models.CharField(max_length=4, db_index=True)
    cpa = models.CharField(max_length=8, blank=True, db_index=True)
    locality = models.CharField(max_length=160)
    province = models.CharField(max_length=160)
    provider_summary = models.JSONField(default=dict)
    synced_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=("postal_code", "locality"))]
