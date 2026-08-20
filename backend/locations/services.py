import math
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from locations.models import PostalLocality


def normalize_postal_code(value: str) -> str:
    normalized = re.sub(r"\s+", "", value or "").upper()
    if not (re.fullmatch(r"\d{4}", normalized) or re.fullmatch(r"[A-Z]\d{4}[A-Z]{3}", normalized)):
        raise ValueError("Postal code must be CP4 or CPA8")
    return normalized


def postal_code_cp4(value: str) -> str:
    normalized = normalize_postal_code(value)
    return normalized if len(normalized) == 4 else normalized[1:5]


def distance_meters(lat1, lon1, lat2, lon2) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_within_distance(lat1, lon1, lat2, lon2, maximum_meters=150) -> bool:
    return distance_meters(lat1, lon1, lat2, lon2) <= maximum_meters


@transaction.atomic
def sync_localities(*, adapter):
    rows = adapter.fetch_localities()
    now = timezone.now()
    for row in rows:
        PostalLocality.objects.update_or_create(
            provider_id=row.provider_id,
            defaults={
                "postal_code": row.postal_code,
                "cpa": row.cpa,
                "locality": row.locality,
                "province": row.province,
                "provider_summary": row.summary,
                "synced_at": now,
            },
        )
    return len(rows)


def lookup_localities(postal_code, *, limit=20):
    normalized = normalize_postal_code(postal_code)
    query = Q(postal_code=postal_code_cp4(normalized))
    if len(normalized) == 8:
        query |= Q(cpa=normalized)
    return list(PostalLocality.objects.filter(query).order_by("locality", "pk")[:limit])


def geocode_address(*, address, adapter):
    result = adapter.geocode(
        street=address.street,
        number=address.number,
        locality=address.locality,
        province=address.province,
        floor=address.floor,
        apartment=address.apartment,
        notes=address.notes,
    )
    address.normalized_address = result.normalized_address
    address.latitude = result.latitude
    address.longitude = result.longitude
    address.geocode_source = address.GeocodeSource.GEOREF
    address.geocode_confidence = result.confidence
    address.geocode_summary = result.summary
    address.needs_review = True
    address.save(
        update_fields=(
            "normalized_address",
            "latitude",
            "longitude",
            "geocode_source",
            "geocode_confidence",
            "geocode_summary",
            "needs_review",
            "updated_at",
        )
    )
    return address


def reverse_geocode_pin(*, address, latitude, longitude, adapter):
    result = adapter.reverse_geocode(latitude=latitude, longitude=longitude)
    moved_far = (
        address.latitude is not None
        and address.longitude is not None
        and not is_within_distance(address.latitude, address.longitude, latitude, longitude, 150)
    )
    address.latitude = latitude
    address.longitude = longitude
    address.geocode_source = address.GeocodeSource.MANUAL
    address.geocode_summary = result.get("summary", {})
    address.needs_review = bool(moved_far)
    address.reviewed_at = None if moved_far else timezone.now()
    address.save(
        update_fields=(
            "latitude",
            "longitude",
            "geocode_source",
            "geocode_summary",
            "needs_review",
            "reviewed_at",
            "updated_at",
        )
    )
    return address, result
