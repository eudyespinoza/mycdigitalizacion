from decimal import Decimal

from django.conf import settings

from commerce.identity import DisabledSIDAdapter, SIDAdapter
from commerce.mercadopago import MercadoPagoAdapter
from commerce.shipping import CorreoArgentinoAdapter, DisabledCarrierAdapter, ShippingPolicy
from providers import ProviderNotConfigured


class UnconfiguredPaymentAdapter:
    live_mode = False
    collector_id = ""

    def create_preference(self, **kwargs):
        del kwargs
        raise ProviderNotConfigured("Mercado Pago no está configurado")

    def fetch_payment(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("Mercado Pago no está configurado")

    def find_payment(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("Mercado Pago no está configurado")

    def refund(self, *args, **kwargs):
        del args, kwargs
        raise ProviderNotConfigured("Mercado Pago no está configurado")


def get_sid_adapter():
    if settings.SID_MODE == "disabled":
        return DisabledSIDAdapter()
    return SIDAdapter(base_url=settings.SID_BASE_URL, token=settings.SID_ACCESS_TOKEN)


def get_payment_adapter():
    if not settings.MERCADOPAGO_ACCESS_TOKEN or not settings.MERCADOPAGO_WEBHOOK_SECRET:
        return UnconfiguredPaymentAdapter()
    adapter = MercadoPagoAdapter(
        access_token=settings.MERCADOPAGO_ACCESS_TOKEN,
        webhook_secret=settings.MERCADOPAGO_WEBHOOK_SECRET,
        back_url_base=settings.PUBLIC_BACKEND_URL,
        live_mode=settings.MERCADOPAGO_LIVE_MODE,
    )
    adapter.collector_id = settings.MERCADOPAGO_COLLECTOR_ID
    return adapter


def get_carrier_adapter():
    if not settings.CORREO_ARGENTINO_ENABLED:
        return DisabledCarrierAdapter()
    base_url = (
        settings.CORREO_ARGENTINO_PRODUCTION_BASE_URL
        if settings.CORREO_ARGENTINO_ENVIRONMENT == "production"
        else settings.CORREO_ARGENTINO_QA_BASE_URL
    )
    return CorreoArgentinoAdapter(
        base_url=base_url,
        username=settings.CORREO_ARGENTINO_USERNAME,
        password=settings.CORREO_ARGENTINO_PASSWORD,
        customer_id=settings.CORREO_ARGENTINO_CUSTOMER_ID,
        origin_postal_code=settings.CORREO_ARGENTINO_ORIGIN_POSTAL_CODE,
    )


def get_shipping_policy():
    threshold = settings.SHIPPING_FREE_THRESHOLD
    return ShippingPolicy(
        surcharge_type=settings.SHIPPING_SURCHARGE_TYPE,
        surcharge_value=Decimal(settings.SHIPPING_SURCHARGE_VALUE),
        free_shipping_threshold=Decimal(threshold) if threshold else None,
    )
