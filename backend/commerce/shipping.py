from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from providers import (
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    UrllibJsonTransport,
)

MONEY = Decimal("0.01")


def _money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def quote_is_valid(expires_at, *, now):
    return expires_at > now


@dataclass(frozen=True)
class ShippingPolicy:
    surcharge_type: str = "exact"
    surcharge_value: Decimal = Decimal("0")
    free_shipping_threshold: Decimal | None = None


@dataclass(frozen=True)
class CarrierQuote:
    base_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal
    service: str
    provider_summary: dict[str, str]


class DisabledCarrierAdapter:
    def quote(self, **kwargs):
        del kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")


class CorreoArgentinoAdapter:
    def __init__(self, *, base_url, username, password, transport=None):
        if not base_url or not username or not password:
            raise ProviderNotConfigured("Correo Argentino no está configurado")
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())
        self._access_token = ""

    def _authenticate(self):
        if self._access_token:
            return self._access_token
        data = self.http.request_json(
            "POST",
            f"{self.base_url}/token",
            payload={"username": self.username, "password": self.password},
        )
        token = str(data.get("access_token", ""))
        if not token:
            raise ProviderInvalidResponse("Correo Argentino no devolvió una sesión válida")
        self._access_token = token
        return token

    def _headers(self):
        return {"Authorization": f"Bearer {self._authenticate()}"}

    def quote(self, *, postal_code, parcels, policy, merchandise_amount=None):
        amounts = []
        services = []
        for parcel in parcels:
            data = self.http.request_json(
                "POST",
                f"{self.base_url}/rates",
                headers=self._headers(),
                payload={"postal_code": postal_code, "parcel": parcel},
            )
            try:
                amounts.append(_money(data["price"]))
                services.append(str(data["service"]))
            except (KeyError, ValueError) as exc:
                raise ProviderInvalidResponse(
                    "Correo Argentino devolvió una tarifa inválida"
                ) from exc
        base = _money(sum(amounts, Decimal("0")))
        if (
            policy.free_shipping_threshold is not None
            and merchandise_amount is not None
            and _money(merchandise_amount) >= _money(policy.free_shipping_threshold)
        ):
            surcharge = Decimal("0.00")
            total = Decimal("0.00")
        else:
            surcharge = (
                _money(base * policy.surcharge_value / Decimal("100"))
                if policy.surcharge_type == "percentage"
                else _money(policy.surcharge_value)
            )
            total = _money(base + surcharge)
        service = services[0] if services and len(set(services)) == 1 else "multi_parcel"
        return CarrierQuote(
            base_amount=base,
            surcharge_amount=surcharge,
            total_amount=total,
            service=service,
            provider_summary={"parcel_count": str(len(parcels)), "service": service},
        )

    def import_shipment(self, payload, *, idempotency_key):
        return self.http.request_json(
            "POST",
            f"{self.base_url}/shipments",
            headers={**self._headers(), "X-Idempotency-Key": idempotency_key},
            payload=payload,
            idempotent=True,
            expected=(200, 201),
        )

    def label(self, shipment_id):
        return self.http.request_json(
            "GET", f"{self.base_url}/shipments/{shipment_id}/label", headers=self._headers()
        )

    def tracking(self, tracking_number):
        return self.http.request_json(
            "GET", f"{self.base_url}/tracking/{tracking_number}", headers=self._headers()
        )


def create_shipping_quote(*, cart, user, address, adapter, policy, now=None):
    from django.utils import timezone

    from commerce.checkout import cart_fingerprint
    from commerce.models import PackageBox, ShippingQuote
    from commerce.packing import Box, PackItem, pack_items
    from commerce.services import calculate_cart_totals

    checked_at = now or timezone.now()
    fingerprint = cart_fingerprint(cart)
    cached = (
        ShippingQuote.objects.filter(
            user=user,
            postal_code=address.postal_code,
            cart_fingerprint=fingerprint,
            expires_at__gt=checked_at,
        )
        .order_by("-created_at")
        .first()
    )
    if cached:
        return cached
    boxes = [
        Box(
            box.code,
            box.inner_length_cm,
            box.inner_width_cm,
            box.inner_height_cm,
            box.tare_weight_grams,
            box.max_weight_grams,
        )
        for box in PackageBox.objects.filter(enabled=True)
    ]
    items = [
        PackItem(
            line.variant.sku,
            line.variant.length_cm,
            line.variant.width_cm,
            line.variant.height_cm,
            line.variant.packaged_weight_grams,
            line.quantity,
        )
        for line in cart.lines.select_related("variant")
    ]
    packed = pack_items(items, boxes)
    if not packed.success:
        raise ValueError("cannot_pack")
    parcels = [
        {
            "box_code": parcel.box_code,
            "weight_grams": parcel.total_weight_grams,
            "item_skus": list(parcel.item_skus),
        }
        for parcel in packed.parcels
    ]
    totals = calculate_cart_totals(cart, at=checked_at)
    rate = adapter.quote(
        postal_code=address.postal_code,
        parcels=parcels,
        policy=policy,
        merchandise_amount=totals.total,
    )
    return ShippingQuote.objects.create(
        user=user,
        service=rate.service,
        postal_code=address.postal_code,
        parcels=parcels,
        base_amount=rate.base_amount,
        surcharge_amount=rate.surcharge_amount,
        total_amount=rate.total_amount,
        cart_fingerprint=fingerprint,
        provider_summary=rate.provider_summary,
        expires_at=checked_at + timezone.timedelta(minutes=15),
    )


def create_order_shipment(*, order, adapter):
    import uuid

    from commerce.models import Shipment

    if hasattr(order, "shipment"):
        return order.shipment
    idempotency_key = uuid.uuid4()
    data = adapter.import_shipment(
        {
            "reference": str(order.public_id),
            "parcels": order.shipping_quote.parcels if order.shipping_quote_id else [],
            "recipient": order.address_snapshot,
        },
        idempotency_key=str(idempotency_key),
    )
    provider_id = str(data.get("id") or "")
    if not provider_id:
        raise ProviderInvalidResponse("Correo Argentino no devolvió un envío válido")
    return Shipment.objects.create(
        order=order,
        provider_id=provider_id,
        idempotency_key=idempotency_key,
        tracking_number=str(data.get("tracking_number") or ""),
        status=str(data.get("status") or "created"),
        provider_summary={"service": str(data.get("service") or "")},
    )
