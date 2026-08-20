from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from providers import ProviderHttpClient, ProviderInvalidResponse, UrllibJsonTransport


@dataclass(frozen=True)
class GeocodeResult:
    normalized_address: str
    latitude: Decimal
    longitude: Decimal
    confidence: Decimal | None
    summary: dict[str, str]


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
            location = match["ubicacion"]
            return GeocodeResult(
                normalized_address=match["nomenclatura"],
                latitude=Decimal(str(location["lat"])),
                longitude=Decimal(str(location["lon"])),
                confidence=Decimal(str(match["confianza"])) if match.get("confianza") else None,
                summary={
                    "province_id": str((match.get("provincia") or {}).get("id", "")),
                    "locality_id": str((match.get("localidad") or {}).get("id", "")),
                },
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderInvalidResponse("GeoRef no encontró una dirección válida") from exc

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

    def fetch_localities(self):
        data = self.http.request_json("GET", self.url)
        rows = data.get("localidades", []) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ProviderInvalidResponse("Andreani devolvió localidades inválidas")
        results = []
        for row in rows:
            try:
                cp = str(row.get("codigoPostal") or row.get("codigo_postal") or "")
                cpa = str(row.get("codigoPostalArgentino") or row.get("cpa") or "").upper()
                locality = str(row.get("localidad") or row.get("nombre") or "")
                province = str(row.get("provincia") or "")
                provider_id = str(row.get("id") or f"{cp}:{locality}:{province}")
                if len(cp) != 4 or not locality or not province:
                    raise ValueError
                results.append(
                    LocalityResult(
                        provider_id,
                        cp,
                        cpa,
                        locality,
                        province,
                        {"provider_id": provider_id},
                    )
                )
            except (AttributeError, ValueError) as exc:
                raise ProviderInvalidResponse("Andreani devolvió una localidad inválida") from exc
        return results
