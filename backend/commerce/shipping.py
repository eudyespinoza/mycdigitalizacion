from __future__ import annotations

import base64
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from django.db import transaction

from providers import (
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    ProviderNotSupported,
    UrllibJsonTransport,
)

MONEY = Decimal("0.01")

PROVINCE_CODES = {
    "SALTA": "A",
    "BUENOS AIRES": "B",
    "PROVINCIA DE BUENOS AIRES": "B",
    "CABA": "C",
    "CIUDAD AUTONOMA DE BUENOS AIRES": "C",
    "SAN LUIS": "D",
    "ENTRE RIOS": "E",
    "LA RIOJA": "F",
    "SANTIAGO DEL ESTERO": "G",
    "CHACO": "H",
    "SAN JUAN": "J",
    "CATAMARCA": "K",
    "LA PAMPA": "L",
    "MENDOZA": "M",
    "MISIONES": "N",
    "FORMOSA": "P",
    "NEUQUEN": "Q",
    "RIO NEGRO": "R",
    "SANTA FE": "S",
    "TUCUMAN": "T",
    "CHUBUT": "U",
    "TIERRA DEL FUEGO": "V",
    "CORRIENTES": "W",
    "CORDOBA": "X",
    "JUJUY": "Y",
    "SANTA CRUZ": "Z",
}


def _province_code(value):
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", str(value or "").upper())
        if not unicodedata.combining(character)
    ).strip()
    if len(normalized) == 1 and normalized in PROVINCE_CODES.values():
        return normalized
    return PROVINCE_CODES.get(normalized, "")


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

    def import_shipment(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def label(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def tracking(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")


class CorreoArgentinoAdapter:
    def __init__(
        self,
        *,
        base_url,
        username,
        password,
        customer_id,
        origin_postal_code,
        transport=None,
    ):
        if not all((base_url, username, password, customer_id, origin_postal_code)):
            raise ProviderNotConfigured("Correo Argentino no está configurado")
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.customer_id = customer_id
        self.origin_postal_code = origin_postal_code
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())
        self._access_token = ""

    def _authenticate(self):
        if self._access_token:
            return self._access_token
        data = self.http.request_json(
            "POST",
            f"{self.base_url}/token",
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            },
        )
        token = str(data.get("token", ""))
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
                payload={
                    "customerId": self.customer_id,
                    "postalCodeOrigin": self.origin_postal_code,
                    "postalCodeDestination": postal_code,
                    "deliveredType": "D",
                    "dimensions": {
                        "weight": int(
                            Decimal(str(parcel["weight_grams"])).to_integral_value(
                                rounding=ROUND_CEILING
                            )
                        ),
                        "height": int(
                            Decimal(str(parcel["height_cm"])).to_integral_value(
                                rounding=ROUND_CEILING
                            )
                        ),
                        "width": int(
                            Decimal(str(parcel["width_cm"])).to_integral_value(
                                rounding=ROUND_CEILING
                            )
                        ),
                        "length": int(
                            Decimal(str(parcel["length_cm"])).to_integral_value(
                                rounding=ROUND_CEILING
                            )
                        ),
                    },
                },
            )
            try:
                rates = [rate for rate in data["rates"] if rate.get("deliveredType") == "D"]
                selected = rates[0]
                amounts.append(_money(selected["price"]))
                services.append(str(selected["productType"]))
            except (IndexError, KeyError, TypeError, ValueError) as exc:
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
            f"{self.base_url}/shipping/import",
            headers={**self._headers(), "X-Idempotency-Key": idempotency_key},
            payload=payload,
            idempotent=True,
            expected=(200, 201),
        )

    def label(self, shipment_id):
        del shipment_id
        raise ProviderNotSupported("MiCorreo no publica un endpoint de etiquetas en el contrato v1")

    def tracking(self, tracking_number):
        return self.http.request_json(
            "GET",
            f"{self.base_url}/shipping/tracking",
            headers=self._headers(),
            payload={"shippingId": tracking_number},
        )


def create_shipping_quote(*, cart, user, address, adapter, policy, now=None):
    from django.utils import timezone

    from commerce.checkout import cart_fingerprint
    from commerce.models import PackageBox, ShippingQuote
    from commerce.packing import Box, PackItem, pack_items
    from commerce.services import calculate_cart_totals

    checked_at = now or timezone.now()
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
        for line in cart.lines.select_related("variant").order_by("variant_id")
    ]
    packed = pack_items(items, boxes)
    if not packed.success:
        raise ValueError("cannot_pack")
    parcels = [
        {
            "box_code": parcel.box_code,
            "weight_grams": parcel.total_weight_grams,
            "item_skus": list(parcel.item_skus),
            "length_cm": str(parcel.length_cm),
            "width_cm": str(parcel.width_cm),
            "height_cm": str(parcel.height_cm),
        }
        for parcel in packed.parcels
    ]
    totals = calculate_cart_totals(cart, at=checked_at)
    fingerprint = cart_fingerprint(cart, address=address, parcels=parcels, at=checked_at)
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


class ShipmentError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _shipment_eligible(order):
    return (
        order.fulfillment_method == order.FulfillmentMethod.SHIPPING
        and order.identity_status == order.IdentityStatus.VERIFIED
        and order.payment_status == order.PaymentStatus.PAID
        and order.fulfillment_status == order.FulfillmentStatus.UNFULFILLED
        and bool(order.shipping_quote_id)
    )


def _parcel_payload(*, order, adapter, parcel, external_id):
    province_code = _province_code(
        order.address_snapshot.get("province_code") or order.address_snapshot.get("province")
    )
    if not province_code:
        raise ShipmentError(
            "shipment_address_invalid",
            "La provincia del domicilio no es válida para Correo Argentino",
        )
    return {
        "customerId": getattr(adapter, "customer_id", "customer"),
        "extOrderId": external_id,
        "orderNumber": str(order.public_id),
        "recipient": {
            "name": order.customer_snapshot.get("name")
            or order.customer_snapshot.get("email", "Cliente"),
            "email": order.customer_snapshot.get("email", ""),
        },
        "shipping": {
            "deliveryType": "D",
            "productType": order.shipping_quote.service
            if order.shipping_quote.service != "multi_parcel"
            else "CP",
            "address": {
                "streetName": order.address_snapshot.get("street", ""),
                "streetNumber": order.address_snapshot.get("number", ""),
                "floor": order.address_snapshot.get("floor", "")[:3],
                "apartment": order.address_snapshot.get("apartment", "")[:3],
                "city": order.address_snapshot.get("locality", ""),
                "provinceCode": province_code,
                "postalCode": order.address_snapshot.get("postal_code", ""),
            },
            "weight": int(parcel["weight_grams"]),
            "declaredValue": float(order.subtotal_snapshot - order.discount_snapshot),
            "height": int(Decimal(parcel["height_cm"]).to_integral_value(rounding=ROUND_CEILING)),
            "length": int(Decimal(parcel["length_cm"]).to_integral_value(rounding=ROUND_CEILING)),
            "width": int(Decimal(parcel["width_cm"]).to_integral_value(rounding=ROUND_CEILING)),
        },
    }


@transaction.atomic
def _prepare_shipment(*, order):
    from commerce.models import Shipment, ShipmentParcelImport

    locked = type(order).objects.select_for_update().get(pk=order.pk)
    existing = Shipment.objects.select_for_update().filter(order=locked).first()
    if existing and existing.status == "imported":
        return existing
    if (
        not _shipment_eligible(locked)
    ):
        raise ShipmentError("shipment_not_eligible", "El pedido todavía no puede despacharse")
    parcels = locked.shipping_quote.parcels
    if not parcels:
        raise ShipmentError("shipment_not_eligible", "El pedido no tiene bultos cotizados")
    idempotency_key = uuid.uuid5(uuid.NAMESPACE_URL, f"shipment:{locked.public_id}")
    shipment = existing or Shipment.objects.create(
        order=locked,
        provider_id=f"{locked.public_id}-1",
        idempotency_key=idempotency_key,
        tracking_number=f"{locked.public_id}-1",
        status="importing",
        provider_summary={"shipping_ids": []},
    )
    for index, parcel in enumerate(parcels, start=1):
        external_id = f"{locked.public_id}-{index}"
        ShipmentParcelImport.objects.get_or_create(
            shipment=shipment,
            parcel_index=index,
            defaults={
                "external_id": external_id,
                "idempotency_key": uuid.uuid5(idempotency_key, str(index)),
                "parcel_snapshot": parcel,
            },
        )
    return shipment


def _import_parcel(*, parcel_import, order, adapter):
    from commerce.models import ShipmentParcelImport

    with transaction.atomic():
        locked = ShipmentParcelImport.objects.select_for_update().get(pk=parcel_import.pk)
        if locked.status == ShipmentParcelImport.Status.IMPORTED:
            return locked
        payload = _parcel_payload(
            order=order,
            adapter=adapter,
            parcel=locked.parcel_snapshot,
            external_id=locked.external_id,
        )
        response = adapter.import_shipment(
            payload,
            idempotency_key=str(locked.idempotency_key),
        )
        if not isinstance(response, dict) or not response.get("createdAt"):
            raise ProviderInvalidResponse("Correo Argentino no confirmó la importación del envío")
        locked.status = ShipmentParcelImport.Status.IMPORTED
        locked.provider_summary = {"created_at": str(response["createdAt"])}
        locked.save(update_fields=("status", "provider_summary", "updated_at"))
        return locked


def create_order_shipment(*, order, adapter):
    from commerce.models import Shipment, ShipmentParcelImport

    shipment = _prepare_shipment(order=order)
    if shipment.status == "imported":
        return shipment
    current_order = type(order).objects.select_related("shipping_quote").get(pk=order.pk)
    for parcel_import in shipment.parcel_imports.order_by("parcel_index"):
        _import_parcel(parcel_import=parcel_import, order=current_order, adapter=adapter)
    with transaction.atomic():
        locked = Shipment.objects.select_for_update().get(pk=shipment.pk)
        imports = list(
            ShipmentParcelImport.objects.select_for_update()
            .filter(shipment=locked)
            .order_by("parcel_index")
        )
        if not imports or any(
            parcel.status != ShipmentParcelImport.Status.IMPORTED for parcel in imports
        ):
            return locked
        shipping_ids = [parcel.external_id for parcel in imports]
        locked.status = "imported"
        locked.provider_summary = {"shipping_ids": shipping_ids}
        locked.save(update_fields=("status", "provider_summary", "updated_at"))
        return locked
