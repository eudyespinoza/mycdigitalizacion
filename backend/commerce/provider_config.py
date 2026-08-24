from decimal import Decimal

from django.conf import settings

from commerce.identity import DisabledSIDAdapter, SIDAdapter
from commerce.mercadopago import MercadoPagoAdapter
from commerce.shipping import (
    AndreaniAdapter,
    CarrierBinding,
    CorreoArgentinoAdapter,
    DisabledCarrierAdapter,
    ShippingPolicy,
)
from providers import ProviderNotConfigured


def _stored(provider):
    from backoffice.integrations import resolved_configuration

    return resolved_configuration(provider)


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
    stored = _stored("sid_renaper")
    if stored is not None:
        base_url = stored["public_config"].get("base_url", "")
        access_token = stored["secrets"].get("access_token", "")
        if not stored["enabled"] or not base_url or not access_token:
            return DisabledSIDAdapter()
        return SIDAdapter(
            base_url=base_url,
            token=access_token,
        )
    if (
        settings.SID_MODE == "disabled"
        or not settings.SID_BASE_URL
        or not settings.SID_ACCESS_TOKEN
    ):
        return DisabledSIDAdapter()
    return SIDAdapter(base_url=settings.SID_BASE_URL, token=settings.SID_ACCESS_TOKEN)


def get_payment_adapter():
    stored = _stored("mercadopago")
    if stored is not None:
        public = stored["public_config"]
        secrets = stored["secrets"]
        if not stored["enabled"] or not secrets.get("webhook_secret"):
            return UnconfiguredPaymentAdapter()
        if secrets.get("refresh_token") or public.get("oauth_grant_type") == "client_credentials":
            from commerce.mercadopago_oauth import resolve_oauth_access_token

            access_token = resolve_oauth_access_token()
        else:
            access_token = secrets.get("access_token", "")
        if not access_token:
            return UnconfiguredPaymentAdapter()
        adapter = MercadoPagoAdapter(
            access_token=access_token,
            webhook_secret=secrets["webhook_secret"],
            back_url_base=settings.PUBLIC_BACKEND_URL,
            live_mode=bool(public.get("live_mode", stored["environment"] == "production")),
        )
        adapter.collector_id = str(public.get("collector_id", ""))
        return adapter
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


MICORREO_BASE_URLS = {
    "sandbox": "https://apitest.correoargentino.com.ar/micorreo/v1",
    "qa": "https://apitest.correoargentino.com.ar/micorreo/v1",
    "production": "https://api.correoargentino.com.ar/micorreo/v1",
}
ANDREANI_BASE_URLS = {
    "sandbox": "https://apisqa.andreani.com",
    "qa": "https://apisqa.andreani.com",
    "production": "https://apis.andreani.com",
}


def get_shipping_policy(provider="correo_argentino"):
    stored = _stored(provider)
    if stored is not None:
        public = stored["public_config"]
        threshold = public.get("free_shipping_threshold", "")
        return ShippingPolicy(
            surcharge_type=public.get("surcharge_type", "exact"),
            surcharge_value=Decimal(str(public.get("surcharge_value", "0"))),
            free_shipping_threshold=Decimal(str(threshold)) if threshold else None,
        )
    threshold = settings.SHIPPING_FREE_THRESHOLD
    return ShippingPolicy(
        surcharge_type=settings.SHIPPING_SURCHARGE_TYPE,
        surcharge_value=Decimal(settings.SHIPPING_SURCHARGE_VALUE),
        free_shipping_threshold=Decimal(threshold) if threshold else None,
    )


def _stored_carrier_binding(provider):
    stored = _stored(provider)
    if stored is None or not stored["enabled"]:
        return None
    public = stored["public_config"]
    secrets = stored["secrets"]
    environment = stored["environment"]
    try:
        if provider == "correo_argentino":
            adapter = CorreoArgentinoAdapter(
                base_url=public.get("base_url") or MICORREO_BASE_URLS[environment],
                username=secrets.get("username", ""),
                password=secrets.get("password", ""),
                customer_id=public.get("customer_id", ""),
                origin_postal_code=public.get("origin_postal_code", ""),
            )
            label = "API MiCorreo"
        elif provider == "andreani":
            adapter = AndreaniAdapter(
                base_url=public.get("base_url") or ANDREANI_BASE_URLS[environment],
                username=secrets.get("username", ""),
                password=secrets.get("password", ""),
                customer_id=public.get("customer_id", ""),
                contract=public.get("contract", ""),
                origin={
                    "postal_code": public.get("origin_postal_code", ""),
                    "street": public.get("origin_street", ""),
                    "number": public.get("origin_number", ""),
                    "city": public.get("origin_city", ""),
                    "province": public.get("origin_province", ""),
                },
                sender={
                    "name": public.get("sender_name", ""),
                    "email": public.get("sender_email", ""),
                    "phone": public.get("sender_phone", ""),
                    "document_type": public.get("sender_document_type", ""),
                    "document_number": public.get("sender_document_number", ""),
                },
            )
            label = "Andreani"
        else:
            return None
    except ProviderNotConfigured:
        return None
    return CarrierBinding(
        provider=provider,
        label=label,
        adapter=adapter,
        policy=get_shipping_policy(provider),
    )


def get_carrier_bindings():
    bindings = [
        binding
        for provider in ("correo_argentino", "andreani")
        if (binding := _stored_carrier_binding(provider)) is not None
    ]
    stored_micorreo = _stored("correo_argentino")
    if (
        not any(binding.provider == "correo_argentino" for binding in bindings)
        and stored_micorreo is None
        and settings.CORREO_ARGENTINO_ENABLED
    ):
        base_url = (
            settings.CORREO_ARGENTINO_PRODUCTION_BASE_URL
            if settings.CORREO_ARGENTINO_ENVIRONMENT == "production"
            else settings.CORREO_ARGENTINO_QA_BASE_URL
        )
        try:
            adapter = CorreoArgentinoAdapter(
                base_url=base_url,
                username=settings.CORREO_ARGENTINO_USERNAME,
                password=settings.CORREO_ARGENTINO_PASSWORD,
                customer_id=settings.CORREO_ARGENTINO_CUSTOMER_ID,
                origin_postal_code=settings.CORREO_ARGENTINO_ORIGIN_POSTAL_CODE,
            )
        except ProviderNotConfigured:
            pass
        else:
            bindings.append(
                CarrierBinding(
                    provider="correo_argentino",
                    label="API MiCorreo",
                    adapter=adapter,
                    policy=get_shipping_policy("correo_argentino"),
                )
            )
    return bindings


def get_carrier_adapter(provider=None):
    bindings = get_carrier_bindings()
    if provider:
        for binding in bindings:
            if binding.provider == provider:
                return binding.adapter
        return DisabledCarrierAdapter()
    return bindings[0].adapter if bindings else DisabledCarrierAdapter()
