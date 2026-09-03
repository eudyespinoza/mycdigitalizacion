from __future__ import annotations

import base64
import hashlib
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from providers import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    ProviderNotSupported,
    ProviderUnavailable,
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


def _plain_decimal(value):
    return format(Decimal(str(value)), "f")


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


@dataclass(frozen=True)
class CarrierBinding:
    provider: str
    label: str
    adapter: object
    policy: ShippingPolicy


@dataclass(frozen=True)
class ShippingQuoteOptions:
    quotes: list[object]
    errors: list[dict[str, str]]
    manual_fallback: bool = False


class DisabledCarrierAdapter:
    def quote(self, **kwargs):
        del kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def import_shipment(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def shipment_status(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def label(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")

    def tracking(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("El envío a domicilio no está configurado")


class CorreoArgentinoAdapter:
    provider = "correo_argentino"
    provider_label = "API MiCorreo"

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

    def test_connection(self):
        self._authenticate()
        return True

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


class AndreaniAdapter:
    provider = "andreani"
    provider_label = "Andreani"

    def __init__(
        self,
        *,
        base_url,
        username,
        password,
        customer_id,
        contract,
        origin,
        sender,
        transport=None,
        token_cache=None,
    ):
        if not all((base_url, username, password, customer_id, contract)):
            raise ProviderNotConfigured("Andreani no está configurado")
        if not all(origin.get(key) for key in ("postal_code", "street", "number", "city")):
            raise ProviderNotConfigured("Completá el domicilio de origen de Andreani")
        if not all(
            sender.get(key)
            for key in ("name", "email", "phone", "document_type", "document_number")
        ):
            raise ProviderNotConfigured("Completá los datos del remitente de Andreani")
        self.base_url = str(base_url).rstrip("/")
        self.username = username
        self.password = password
        self.customer_id = customer_id
        self.contract = contract
        self.origin = origin
        self.sender = sender
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())
        self.token_cache = token_cache or cache
        self._access_token = ""
        token_identity = f"{self.base_url}\0{self.username}\0{self.password}"
        token_digest = hashlib.sha256(token_identity.encode()).hexdigest()
        self._token_cache_key = f"andreani:token:{token_digest}"

    def _authenticate(self):
        if self._access_token:
            return self._access_token
        cached_token = self.token_cache.get(self._token_cache_key, "")
        if cached_token:
            self._access_token = str(cached_token)
            return self._access_token
        credentials = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode("ascii")
        response = self.http.request_json_response(
            "GET",
            f"{self.base_url}/login",
            headers={"Authorization": f"Basic {credentials}"},
        )
        token = str(
            response.headers.get("x-authorization-token")
            or (response.body.get("token") if isinstance(response.body, dict) else "")
            or ""
        )
        if not token:
            raise ProviderInvalidResponse("Andreani no devolvió una sesión válida")
        self._access_token = token
        self.token_cache.set(self._token_cache_key, token, timeout=23 * 60 * 60)
        return token

    def _invalidate_token(self):
        self._access_token = ""
        self.token_cache.delete(self._token_cache_key)

    def _headers(self):
        return {"x-authorization-token": self._authenticate()}

    def _request_json(self, method, url, *, headers=None, payload=None, params=None, **kwargs):
        for attempt in range(2):
            try:
                return self.http.request_json(
                    method,
                    url,
                    headers={**self._headers(), **(headers or {})},
                    payload=payload,
                    params=params,
                    **kwargs,
                )
            except ProviderAuthenticationError:
                self._invalidate_token()
                if attempt:
                    raise
        raise ProviderAuthenticationError("Andreani rechazó la autenticación")

    def _request_bytes(self, method, url, *, headers=None, **kwargs):
        for attempt in range(2):
            try:
                return self.http.request_bytes(
                    method,
                    url,
                    headers={**self._headers(), **(headers or {})},
                    **kwargs,
                )
            except ProviderAuthenticationError:
                self._invalidate_token()
                if attempt:
                    raise
        raise ProviderAuthenticationError("Andreani rechazó la autenticación")

    def test_connection(self):
        self._authenticate()
        return True

    def quote(self, *, postal_code, parcels, policy, merchandise_amount=None):
        params = {
            "cpDestino": postal_code,
            "contrato": self.contract,
            "cliente": self.customer_id,
        }
        declared_value = _money(merchandise_amount or 0)
        for index, parcel in enumerate(parcels):
            length = Decimal(str(parcel["length_cm"]))
            width = Decimal(str(parcel["width_cm"]))
            height = Decimal(str(parcel["height_cm"]))
            weight = Decimal(str(parcel["weight_grams"])) / Decimal("1000")
            prefix = f"bultos[{index}]"
            params.update(
                {
                    f"{prefix}[volumen]": int(
                        (length * width * height).to_integral_value(rounding=ROUND_CEILING)
                    ),
                    f"{prefix}[kilos]": f"{weight:.3f}",
                    f"{prefix}[altoCm]": _plain_decimal(height),
                    f"{prefix}[largoCm]": _plain_decimal(length),
                    f"{prefix}[anchoCm]": _plain_decimal(width),
                    f"{prefix}[valorDeclarado]": f"{declared_value:.2f}",
                }
            )
        data = self._request_json(
            "GET",
            f"{self.base_url}/v1/tarifas",
            params=params,
        )
        try:
            base = _money(data["tarifaConIva"]["total"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderInvalidResponse("Andreani devolvió una tarifa inválida") from exc
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
        return CarrierQuote(
            base_amount=base,
            surcharge_amount=surcharge,
            total_amount=total,
            service="andreani_domicilio",
            provider_summary={
                "parcel_count": str(len(parcels)),
                "service": "andreani_domicilio",
                "label": self.provider_label,
            },
        )

    def import_shipment(self, payload, *, idempotency_key):
        parcel = payload["parcel"]
        recipient = payload["recipient"]
        destination = payload["destination"]
        remote_payload = {
            "contrato": self.contract,
            "idDeProducto": payload["external_id"],
            "origen": {
                "postal": {
                    "codigoPostal": self.origin["postal_code"],
                    "calle": self.origin["street"],
                    "numero": self.origin["number"],
                    "localidad": self.origin["city"],
                    "provincia": self.origin.get("province", ""),
                    "pais": "Argentina",
                }
            },
            "destino": {
                "postal": {
                    "codigoPostal": destination["postal_code"],
                    "calle": destination["street"],
                    "numero": destination["number"],
                    "localidad": destination["city"],
                    "provincia": destination.get("province", ""),
                    "pais": "Argentina",
                }
            },
            "remitente": {
                "nombreCompleto": self.sender["name"],
                "eMail": self.sender["email"],
                "documentoTipo": self.sender["document_type"],
                "documentoNumero": self.sender["document_number"],
                "telefonos": [{"tipo": 1, "numero": self.sender["phone"]}],
            },
            "destinatario": {
                "nombreCompleto": recipient["name"],
                "eMail": recipient["email"],
                "documentoTipo": recipient["document_type"],
                "documentoNumero": recipient["document_number"],
                "telefonos": [{"tipo": 1, "numero": recipient["phone"]}],
            },
            "bultos": [
                {
                    "kilos": f"{Decimal(str(parcel['weight_grams'])) / Decimal('1000'):.3f}",
                    "largoCm": str(parcel["length_cm"]),
                    "anchoCm": str(parcel["width_cm"]),
                    "altoCm": str(parcel["height_cm"]),
                    "valorDeclaradoConImpuestos": str(parcel["declared_value"]),
                }
            ],
        }
        data = self._request_json(
            "POST",
            f"{self.base_url}/v2/ordenes-de-envio",
            headers={"X-Idempotency-Key": idempotency_key},
            payload=remote_payload,
            idempotent=True,
            expected=(200, 201),
        )
        return self._normalize_order(data)

    def _normalize_order(self, data):
        entry = data[0] if isinstance(data, list) and data else data
        if not isinstance(entry, dict):
            raise ProviderInvalidResponse("Andreani no confirmó la orden de envío")
        provider_id = str(
            entry.get("numeroAndreani")
            or entry.get("numeroDeEnvio")
            or entry.get("agrupadorDeBultos")
            or ""
        )
        if not provider_id:
            raise ProviderInvalidResponse("Andreani no devolvió el número de envío")
        provider_status = str(entry.get("estado") or "")
        normalized_status = "".join(
            character
            for character in unicodedata.normalize("NFKD", provider_status.casefold())
            if not unicodedata.combining(character)
        )
        if normalized_status in {"creado", "creada"}:
            state = "created"
        elif normalized_status in {"rechazado", "rechazada"}:
            state = "rejected"
        elif normalized_status in {"", "pendiente", "solicitado"}:
            state = "submitted"
        else:
            raise ProviderInvalidResponse("Andreani devolvió un estado de envío inválido")
        return {
            "provider_id": provider_id,
            "tracking_number": str(entry.get("numeroAndreani") or provider_id),
            "state": state,
            "provider_status": provider_status,
            "created_at": str(entry.get("fechaCreacion") or ""),
            "rejection_reason": str(
                entry.get("motivoRechazo") or entry.get("motivo") or entry.get("mensaje") or ""
            ),
        }

    def shipment_status(self, shipment_id):
        data = self._request_json(
            "GET",
            f"{self.base_url}/v2/ordenes-de-envio/{shipment_id}",
        )
        return self._normalize_order(data)

    def label(self, shipment_id):
        document = self._request_bytes(
            "GET",
            f"{self.base_url}/v2/ordenes-de-envio/{shipment_id}/etiquetas",
            headers={"Accept": "application/pdf"},
        )
        if not document.startswith(b"%PDF-"):
            raise ProviderInvalidResponse("Andreani devolvió una etiqueta inválida")
        return document

    def tracking(self, tracking_number):
        return self._request_json(
            "GET",
            f"{self.base_url}/v3/envios/{tracking_number}",
        )


def _packed_quote_context(*, cart, address, checked_at):
    from commerce.checkout import cart_fingerprint
    from commerce.models import PackageBox
    from commerce.packing import Box, PackItem, pack_items
    from commerce.services import calculate_cart_totals

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
    return parcels, totals, fingerprint


def create_shipping_quote(
    *, cart, user, address, adapter, policy, provider=None, label=None, now=None
):
    from django.utils import timezone

    from commerce.models import ShippingQuote

    checked_at = now or timezone.now()
    parcels, totals, fingerprint = _packed_quote_context(
        cart=cart, address=address, checked_at=checked_at
    )
    provider_key = provider or getattr(adapter, "provider", "correo_argentino")
    cached = (
        ShippingQuote.objects.filter(
            user=user,
            provider=provider_key,
            postal_code=address.postal_code,
            cart_fingerprint=fingerprint,
            expires_at__gt=checked_at,
            amount_pending=False,
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
        provider=provider_key,
        service=rate.service,
        postal_code=address.postal_code,
        parcels=parcels,
        base_amount=rate.base_amount,
        surcharge_amount=rate.surcharge_amount,
        total_amount=rate.total_amount,
        cart_fingerprint=fingerprint,
        provider_summary={
            **rate.provider_summary,
            "label": label
            or rate.provider_summary.get("label")
            or getattr(adapter, "provider_label", provider_key),
        },
        expires_at=checked_at + timezone.timedelta(minutes=15),
    )


def _manual_shipping_quote(*, cart, user, address, checked_at):
    from django.utils import timezone

    from commerce.checkout import cart_fingerprint
    from commerce.models import ShippingQuote

    # A manual agreement does not need a carrier-ready package plan. Requiring
    # boxes here prevents the intended fallback from existing precisely when
    # shipping has not been configured yet.
    parcels = []
    fingerprint = cart_fingerprint(
        cart, address=address, parcels=parcels, at=checked_at
    )
    cached = (
        ShippingQuote.objects.filter(
            user=user,
            provider="manual",
            postal_code=address.postal_code,
            cart_fingerprint=fingerprint,
            amount_pending=True,
            expires_at__gt=checked_at,
        )
        .order_by("-created_at")
        .first()
    )
    if cached:
        return cached
    return ShippingQuote.objects.create(
        user=user,
        provider="manual",
        service="a_convenir",
        postal_code=address.postal_code,
        parcels=parcels,
        base_amount=Decimal("0.00"),
        surcharge_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        amount_pending=True,
        cart_fingerprint=fingerprint,
        provider_summary={
            "label": "Envío a acordar",
            "status": "pending_agreement",
            "parcel_count": str(len(parcels)),
        },
        expires_at=checked_at + timezone.timedelta(days=7),
    )


def create_shipping_quote_options(*, cart, user, address, bindings, now=None):
    """Quote every configured carrier; manual fallback is allowed only when there are none."""
    from django.utils import timezone

    checked_at = now or timezone.now()
    if not bindings:
        return ShippingQuoteOptions(
            quotes=[
                _manual_shipping_quote(
                    cart=cart,
                    user=user,
                    address=address,
                    checked_at=checked_at,
                )
            ],
            errors=[],
            manual_fallback=True,
        )
    quotes = []
    errors = []
    first_error = None
    for binding in bindings:
        try:
            quotes.append(
                create_shipping_quote(
                    cart=cart,
                    user=user,
                    address=address,
                    adapter=binding.adapter,
                    policy=binding.policy,
                    provider=binding.provider,
                    label=binding.label,
                    now=checked_at,
                )
            )
        except ProviderError as exc:
            first_error = first_error or exc
            errors.append(
                {
                    "provider": binding.provider,
                    "label": binding.label,
                    "code": exc.code,
                }
            )
    if not quotes:
        raise first_error or ProviderUnavailable("No pudimos obtener tarifas de envío")
    return ShippingQuoteOptions(quotes=quotes, errors=errors)


@transaction.atomic
def resolve_manual_shipping_cost(*, order, amount, actor, reason):
    """Finalize a manually agreed cost before any payment preference exists."""
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    from commerce.models import NotificationAttempt, OrderAuditEvent, ShippingQuote

    normalized_reason = str(reason or "").strip()
    resolved_amount = _money(amount)
    if not normalized_reason or len(normalized_reason) > 500:
        raise ValidationError("Indicá un motivo válido para el costo acordado")
    if resolved_amount < 0:
        raise ValidationError("El costo de envío no puede ser negativo")
    locked = type(order).objects.select_for_update().get(pk=order.pk)
    if not actor.is_staff or not actor.has_perm("commerce.set_shipping_cost_order"):
        raise ValidationError("Sólo un operador puede definir el costo de envío")
    if locked.payment_transactions.exists():
        raise ValidationError("El pedido ya inició el pago")
    if not locked.shipping_quote_id:
        raise ValidationError("Este pedido no espera un costo de envío acordado")
    quote = ShippingQuote.objects.select_for_update().get(pk=locked.shipping_quote_id)
    if (
        quote.provider != "manual"
        or locked.shipping_cost_status != locked.ShippingCostStatus.PENDING_AGREEMENT
    ):
        raise ValidationError("Este pedido no espera un costo de envío acordado")
    quote.base_amount = resolved_amount
    quote.surcharge_amount = Decimal("0.00")
    quote.total_amount = resolved_amount
    quote.amount_pending = False
    quote.expires_at = timezone.now() + timezone.timedelta(days=7)
    quote.provider_summary = {
        **quote.provider_summary,
        "status": "ready",
        "resolved_by": str(actor.pk),
    }
    quote.save(
        update_fields=(
            "base_amount",
            "surcharge_amount",
            "total_amount",
            "amount_pending",
            "provider_summary",
            "expires_at",
        )
    )
    locked.shipping_amount_snapshot = resolved_amount
    locked.total_snapshot = _money(
        locked.subtotal_snapshot - locked.discount_snapshot + resolved_amount
    )
    locked.shipping_cost_status = locked.ShippingCostStatus.READY
    locked._save_shipping_cost_resolution()
    OrderAuditEvent.objects.create(
        order=locked,
        kind="shipping_cost_agreed",
        data={"amount": f"{resolved_amount:.2f}", "reason": normalized_reason},
        actor=actor,
    )
    NotificationAttempt.objects.get_or_create(
        kind="shipping_cost_ready",
        reference=str(locked.public_id),
        defaults={
            "payload": {
                "order_id": str(locked.public_id),
                "account_path": f"/pedidos/{locked.public_id}",
            }
        },
    )
    return locked


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
        and order.shipping_quote.provider != "manual"
    )


def _parcel_payload(*, order, adapter, parcel, external_id):
    if getattr(adapter, "provider", "") == "andreani":
        try:
            document_number = order.user.customer_profile.get_dni()
        except Exception as exc:
            raise ShipmentError(
                "shipment_customer_invalid",
                "El cliente no tiene un DNI disponible para Andreani",
            ) from exc
        if not document_number:
            raise ShipmentError(
                "shipment_customer_invalid",
                "El cliente no tiene un DNI disponible para Andreani",
            )
        return {
            "external_id": external_id,
            "recipient": {
                "name": order.customer_snapshot.get("name")
                or order.customer_snapshot.get("email", "Cliente"),
                "email": order.customer_snapshot.get("email", ""),
                "document_type": "DNI",
                "document_number": document_number,
                "phone": order.customer_snapshot.get("phone", ""),
            },
            "destination": {
                "postal_code": order.address_snapshot.get("postal_code", ""),
                "street": order.address_snapshot.get("street", ""),
                "number": order.address_snapshot.get("number", ""),
                "city": order.address_snapshot.get("locality", ""),
                "province": order.address_snapshot.get("province", ""),
            },
            "parcel": {
                "weight_grams": parcel["weight_grams"],
                "length_cm": parcel["length_cm"],
                "width_cm": parcel["width_cm"],
                "height_cm": parcel["height_cm"],
                "declared_value": f"{order.subtotal_snapshot - order.discount_snapshot:.2f}",
            },
        }
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
        provider=locked.shipping_quote.provider,
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


def _poll_delay_minutes(poll_attempts):
    return min(2 ** max(poll_attempts, 0), 15)


def _apply_parcel_response(*, parcel_import, response, now):
    from commerce.models import ShipmentParcelImport

    if not isinstance(response, dict):
        raise ProviderInvalidResponse("El transportista no confirmó el envío")
    state = str(response.get("state") or "")
    if not state and response.get("createdAt"):
        state = "created"
    if state not in {"submitted", "created", "rejected"}:
        raise ProviderInvalidResponse("El transportista devolvió un estado de envío inválido")

    provider_id = str(
        response.get("provider_id")
        or response.get("tracking_number")
        or parcel_import.provider_id
        or ""
    )
    if state in {"submitted", "rejected"} and not provider_id:
        raise ProviderInvalidResponse("El transportista no devolvió el identificador del envío")

    summary = dict(parcel_import.provider_summary or {})
    summary.update(
        {
            "provider_id": provider_id,
            "created_at": str(response.get("created_at") or response.get("createdAt") or ""),
            "tracking_number": str(response.get("tracking_number") or provider_id),
            "provider_status": str(
                response.get("provider_status") or response.get("status") or ""
            ),
            "rejection_reason": str(response.get("rejection_reason") or "").strip()[:500],
        }
    )
    parcel_import.provider_id = provider_id
    parcel_import.provider_summary = summary
    if state == "created":
        parcel_import.status = ShipmentParcelImport.Status.IMPORTED
        parcel_import.next_poll_at = None
    elif state == "rejected":
        parcel_import.status = ShipmentParcelImport.Status.REJECTED
        parcel_import.next_poll_at = None
    else:
        parcel_import.status = ShipmentParcelImport.Status.SUBMITTED
        parcel_import.next_poll_at = now + timezone.timedelta(
            minutes=_poll_delay_minutes(parcel_import.poll_attempts)
        )


def _import_parcel(*, parcel_import, order, adapter, now=None, force_poll=False):
    from commerce.models import ShipmentParcelImport

    now = now or timezone.now()
    poll_error = None
    with transaction.atomic():
        locked = ShipmentParcelImport.objects.select_for_update().get(pk=parcel_import.pk)
        if locked.status in {
            ShipmentParcelImport.Status.IMPORTED,
            ShipmentParcelImport.Status.REJECTED,
        }:
            return locked
        if locked.status in {
            ShipmentParcelImport.Status.SUBMITTED,
            ShipmentParcelImport.Status.ATTENTION_REQUIRED,
        }:
            if not force_poll and now - locked.created_at >= timezone.timedelta(hours=24):
                locked.status = ShipmentParcelImport.Status.ATTENTION_REQUIRED
                locked.next_poll_at = None
                locked.save(update_fields=("status", "next_poll_at", "updated_at"))
                return locked
            if not force_poll and locked.next_poll_at and locked.next_poll_at > now:
                return locked
            try:
                response = adapter.shipment_status(locked.provider_id)
            except ProviderError as exc:
                locked.poll_attempts += 1
                locked.next_poll_at = now + timezone.timedelta(
                    minutes=_poll_delay_minutes(locked.poll_attempts)
                )
                locked.save(update_fields=("poll_attempts", "next_poll_at", "updated_at"))
                poll_error = exc
            else:
                locked.poll_attempts += 1
        else:
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
        if poll_error is None:
            _apply_parcel_response(parcel_import=locked, response=response, now=now)
            locked.save(
                update_fields=(
                    "status",
                    "provider_id",
                    "poll_attempts",
                    "next_poll_at",
                    "provider_summary",
                    "updated_at",
                )
            )
        result = locked
    if poll_error is not None:
        raise poll_error
    return result


def create_order_shipment(*, order, adapter, force_poll=False):
    from commerce.models import Shipment, ShipmentParcelImport

    shipment = _prepare_shipment(order=order)
    if shipment.status == "imported":
        return shipment
    current_order = type(order).objects.select_related("shipping_quote").get(pk=order.pk)
    for parcel_import in shipment.parcel_imports.order_by("parcel_index"):
        _import_parcel(
            parcel_import=parcel_import,
            order=current_order,
            adapter=adapter,
            force_poll=force_poll,
        )
    with transaction.atomic():
        locked = Shipment.objects.select_for_update().get(pk=shipment.pk)
        imports = list(
            ShipmentParcelImport.objects.select_for_update()
            .filter(shipment=locked)
            .order_by("parcel_index")
        )
        if not imports:
            return locked
        shipping_ids = [
            parcel.provider_summary.get("tracking_number")
            or parcel.provider_id
            or parcel.external_id
            for parcel in imports
        ]
        if all(parcel.status == ShipmentParcelImport.Status.IMPORTED for parcel in imports):
            locked.status = "imported"
        elif any(parcel.status == ShipmentParcelImport.Status.REJECTED for parcel in imports):
            locked.status = "rejected"
        elif any(
            parcel.status == ShipmentParcelImport.Status.ATTENTION_REQUIRED for parcel in imports
        ):
            locked.status = "attention_required"
        else:
            locked.status = "importing"
        if shipping_ids:
            locked.provider_id = shipping_ids[0]
            locked.tracking_number = shipping_ids[0]
        locked.label_url = ""
        locked.provider_summary = {**(locked.provider_summary or {}), "shipping_ids": shipping_ids}
        locked.save(
            update_fields=(
                "status",
                "provider_id",
                "tracking_number",
                "label_url",
                "provider_summary",
                "updated_at",
            )
        )
        return locked


def refresh_shipment_tracking(*, shipment, adapter):
    if shipment.status in {"importing", "attention_required"}:
        shipment = create_order_shipment(
            order=shipment.order,
            adapter=adapter,
            force_poll=True,
        )
    if shipment.status in {"importing", "rejected", "attention_required"}:
        return shipment
    if not shipment.tracking_number:
        return shipment
    tracking = adapter.tracking(shipment.tracking_number)
    entry = tracking[0] if isinstance(tracking, list) and tracking else tracking
    events = entry.get("events", []) if isinstance(entry, dict) else []
    last_event = events[0] if events else {}
    shipment.status = str(
        last_event.get("event")
        or (entry.get("estado") if isinstance(entry, dict) else "")
        or shipment.status
    ).lower()
    shipment.provider_summary = {
        **(shipment.provider_summary or {}),
        "last_event": str(last_event.get("event") or ""),
    }
    shipment.save(update_fields=("status", "provider_summary", "updated_at"))
    return shipment
