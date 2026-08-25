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
def sync_localities(*, adapter, postal_code=None):
    provider_postal_code = postal_code_cp4(postal_code) if postal_code else None
    rows = adapter.fetch_localities(postal_code=provider_postal_code)
    now = timezone.now()
    records = [
        PostalLocality(
            provider_id=row.provider_id,
            postal_code=row.postal_code,
            cpa=row.cpa,
            locality=row.locality,
            province=row.province,
            provider_summary=row.summary,
            synced_at=now,
        )
        for row in rows
    ]
    PostalLocality.objects.bulk_create(
        records,
        batch_size=1000,
        update_conflicts=True,
        unique_fields=("provider_id",),
        update_fields=(
            "postal_code",
            "cpa",
            "locality",
            "province",
            "provider_summary",
            "synced_at",
        ),
    )
    return len(rows)


def lookup_localities(postal_code, *, limit=20):
    normalized = normalize_postal_code(postal_code)
    query = Q(cpa=normalized) if len(normalized) == 8 else Q(postal_code=normalized)
    return list(PostalLocality.objects.filter(query).order_by("locality", "pk")[:limit])


def geocode_address(*, address, adapter):
    result = adapter.geocode(
        street=address.street,
        number=address.number,
        locality=address.locality,
        province=address.province,
    )
    address.normalized_address = result.normalized_address
    address.latitude = result.latitude
    address.longitude = result.longitude
    address.geocode_source = address.GeocodeSource(result.source)
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
    address.geocode_summary = {
        **result.get("summary", {}),
        "reverse_location": {
            "locality": str(result.get("locality", "")),
            "province": str(result.get("province", "")),
        },
    }
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


@transaction.atomic
def confirm_address(*, address, latitude, longitude, address_choice, tolerance_meters=2):
    locked = type(address).objects.select_for_update().get(pk=address.pk)
    if locked.geocode_source not in {
        locked.GeocodeSource.GEOREF,
        locked.GeocodeSource.MANUAL,
        locked.GeocodeSource.OPENSTREETMAP,
    }:
        raise ValueError("address_not_geocoded")
    if locked.latitude is None or locked.longitude is None:
        raise ValueError("address_coordinates_missing")
    if (
        locked.geocode_source in {
            locked.GeocodeSource.GEOREF,
            locked.GeocodeSource.OPENSTREETMAP,
        }
        and (locked.geocode_summary or {}).get("precision") == "locality"
    ):
        raise ValueError("address_requires_pin_adjustment")
    if not is_within_distance(
        locked.latitude,
        locked.longitude,
        latitude,
        longitude,
        tolerance_meters,
    ):
        raise ValueError("address_coordinates_changed")
    allowed_choices = (
        {"written", "reverse"}
        if locked.geocode_source == locked.GeocodeSource.MANUAL
        else {"written"}
    )
    if address_choice not in allowed_choices:
        raise ValueError("address_choice_mismatch")
    reviewed_at = timezone.now()
    summary = dict(locked.geocode_summary or {})
    summary["confirmation"] = {
        "address_choice": address_choice,
        "confirmed_at": reviewed_at.isoformat(),
    }
    update_fields = ["geocode_summary", "needs_review", "reviewed_at", "updated_at"]
    if address_choice == "reverse":
        reverse_location = summary.get("reverse_location") or {}
        normalized_parts = [
            str(reverse_location.get(field, "")).strip()
            for field in ("locality", "province")
        ]
        normalized_address = ", ".join(part for part in normalized_parts if part)
        if normalized_address:
            locked.normalized_address = normalized_address
            update_fields.append("normalized_address")
    locked.geocode_summary = summary
    locked.needs_review = False
    locked.reviewed_at = reviewed_at
    locked.save(update_fields=update_fields)
    return locked
