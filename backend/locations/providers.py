from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from providers import (
    ProviderError,
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderUnavailable,
    UrllibJsonTransport,
)


@dataclass(frozen=True)
class GeocodeResult:
    normalized_address: str
    latitude: Decimal
    longitude: Decimal
    confidence: Decimal | None
    summary: dict[str, str]
    source: str = "georef"


class FallbackGeocoder:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback

    def geocode(self, **address):
        primary_result = self.primary.geocode(**address)
        if primary_result.summary.get("precision") != "locality":
            return primary_result
        try:
            return self.fallback.geocode(**address)
        except ProviderError:
            return primary_result


class OpenStreetMapAdapter:
    def __init__(
        self,
        *,
        transport=None,
        base_url=None,
        user_agent=None,
        cache_backend=cache,
    ):
        self.base_url = (base_url or settings.NOMINATIM_BASE_URL).rstrip("/")
        self.user_agent = user_agent or (
            f"mycdigitalizacion/1.0 (+{settings.PUBLIC_BACKEND_URL})"
        )
        self.cache = cache_backend
        self.http = ProviderHttpClient(transport or UrllibJsonTransport(), retries=0)

    def geocode(
        self,
        *,
        street,
        number,
        locality,
        province,
        floor="",
        apartment="",
        notes="",
    ):
        del floor, apartment, notes
        query = f"{street} {number}, {locality}, {province}, Argentina"
        cache_key = f"locations:nominatim:{hashlib.sha256(query.casefold().encode()).hexdigest()}"
        cached = self.cache.get(cache_key)
        if cached:
            return self._parse(cached, expected_number=str(number))
        if not self.cache.add("locations:nominatim:request-rate", True, timeout=1):
            raise ProviderUnavailable("OpenStreetMap está temporalmente ocupado")
        data = self.http.request_json(
            "GET",
            f"{self.base_url}/search",
            headers={"User-Agent": self.user_agent},
            params={
                "format": "jsonv2",
                "q": query,
                "countrycodes": "ar",
                "addressdetails": 1,
                "limit": 1,
            },
        )
        if not isinstance(data, list) or not data:
            raise ProviderInvalidResponse("OpenStreetMap no encontró la dirección")
        result = self._parse(data[0], expected_number=str(number))
        self.cache.set(cache_key, data[0], timeout=30 * 24 * 60 * 60)
        return result

    @staticmethod
    def _parse(match, *, expected_number):
        try:
            details = match.get("address") or {}
            returned_number = str(details.get("house_number") or "").strip()
            if returned_number.casefold() != expected_number.strip().casefold():
                raise ValueError
            return GeocodeResult(
                normalized_address=str(match["display_name"]),
                latitude=Decimal(str(match["lat"])),
                longitude=Decimal(str(match["lon"])),
                confidence=None,
                summary={
                    "precision": "address",
                    "road": str(details.get("road") or ""),
                    "house_number": returned_number,
                },
                source="openstreetmap",
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ProviderInvalidResponse(
                "OpenStreetMap no devolvió la altura exacta"
            ) from exc


class GeoRefAdapter:
    base_url = "https://apis.datos.gob.ar/georef/api"

    def __init__(self, *, transport=None):
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())

    def geocode(
        self,
        *,
        street,
        number,
        locality,
        province,
        floor="",
        apartment="",
        notes="",
    ):
        del floor, apartment, notes
        data = self.http.request_json(
            "GET",
            f"{self.base_url}/direcciones",
            params={
                "direccion": f"{street} {number}".strip(),
                "localidad": locality,
                "provincia": province,
                "max": 1,
            },
        )
        try:
            match = data["direcciones"][0]
        except (KeyError, IndexError, TypeError):
            return self._locality_center(
                street=street,
                number=number,
                locality=locality,
                province=province,
            )
        try:
            location = match["ubicacion"]
            return GeocodeResult(
                normalized_address=match["nomenclatura"],
                latitude=Decimal(str(location["lat"])),
                longitude=Decimal(str(location["lon"])),
                confidence=Decimal(str(match["confianza"])) if match.get("confianza") else None,
                summary={
                    "province_id": str((match.get("provincia") or {}).get("id", "")),
                    "locality_id": str((match.get("localidad") or {}).get("id", "")),
                    "precision": "address",
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderInvalidResponse("GeoRef devolvió una dirección inválida") from exc

    def _locality_center(self, *, street, number, locality, province):
        data = self.http.request_json(
            "GET",
            f"{self.base_url}/localidades",
            params={
                "nombre": locality,
                "provincia": province,
                "campos": "id,nombre,centroide,provincia",
                "max": 5,
            },
        )
        try:
            match = data["localidades"][0]
            center = match["centroide"]
            matched_province = match.get("provincia") or {}
            matched_locality = str(match["nombre"])
            matched_province_name = str(matched_province.get("nombre") or province)
            return GeocodeResult(
                normalized_address=(
                    f"{street} {number}, {matched_locality}, {matched_province_name}"
                ),
                latitude=Decimal(str(center["lat"])),
                longitude=Decimal(str(center["lon"])),
                confidence=None,
                summary={
                    "province_id": str(matched_province.get("id", "")),
                    "locality_id": str(match.get("id", "")),
                    "precision": "locality",
                },
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderInvalidResponse(
                "GeoRef no encontró la dirección ni la localidad"
            ) from exc

    def reverse_geocode(self, *, latitude, longitude):
        data = self.http.request_json(
            "GET",
            f"{self.base_url}/ubicacion",
            params={"lat": latitude, "lon": longitude},
        )
        try:
            location = data["ubicacion"]
            province = location.get("provincia") or {}
            department = location.get("departamento") or {}
            return {
                "province": province.get("nombre", ""),
                "locality": department.get("nombre", ""),
                "latitude": str(location["lat"]),
                "longitude": str(location["lon"]),
                "summary": {
                    "province_id": str(province.get("id", "")),
                    "department_id": str(department.get("id", "")),
                },
            }
        except (KeyError, TypeError) as exc:
            raise ProviderInvalidResponse("GeoRef devolvió una ubicación inválida") from exc


@dataclass(frozen=True)
class LocalityResult:
    provider_id: str
    postal_code: str
    cpa: str
    locality: str
    province: str
    summary: dict[str, str]


class AndreaniLocalitiesAdapter:
    url = "https://apis.andreani.com/v1/localidades"

    def __init__(self, *, transport=None):
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())

    def fetch_localities(self, *, postal_code=None):
        params = {"codigosPostales": postal_code} if postal_code else None
        data = self.http.request_json("GET", self.url, params=params)
        rows = data.get("localidades", []) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ProviderInvalidResponse("Andreani devolvió localidades inválidas")
        results = []
        for row in rows:
            try:
                postal_codes = row.get("codigosPostales")
                if not isinstance(postal_codes, list):
                    postal_codes = [row.get("codigoPostal") or row.get("codigo_postal") or ""]
                cpa = str(row.get("codigoPostalArgentino") or row.get("cpa") or "").upper()
                locality = str(row.get("localidad") or row.get("nombre") or "")
                province = str(row.get("provincia") or "")
                source_id = str(row.get("idDeProvLocalidad") or row.get("id") or "")
                if not locality or not province:
                    raise ValueError
                for value in postal_codes:
                    cp = str(value)
                    if len(cp) != 4 or not cp.isdigit():
                        raise ValueError
                    identity = f"{source_id}|{cp}|{locality}|{province}"
                    provider_id = f"andreani:{hashlib.sha256(identity.encode()).hexdigest()[:32]}"
                    results.append(
                        LocalityResult(
                            provider_id,
                            cp,
                            cpa,
                            locality,
                            province,
                            {"provider_id": source_id},
                        )
                    )
            except (AttributeError, ValueError) as exc:
                raise ProviderInvalidResponse("Andreani devolvió una localidad inválida") from exc
        return results
