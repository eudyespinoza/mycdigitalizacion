import base64
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from tests.test_checkout_domain import ApprovedSID, PreferencePayment, make_customer
from tests.test_commerce_domain import make_variant


class ContractTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "json": json,
                "params": params,
                "timeout": timeout,
            }
        )
        return next(self.responses)


def test_provider_http_client_preserves_response_headers_and_binary_bodies():
    from providers import ProviderHttpClient

    transport = ContractTransport(
        [
            (200, {"X-Authorization-Token": "andreani-jwt"}, {"ok": True}),
            (200, {"Content-Type": "application/pdf"}, b"%PDF-1.4\nlabel"),
        ]
    )
    client = ProviderHttpClient(transport)

    response = client.request_json_response("GET", "https://provider.example.test/login")

    assert response.headers["x-authorization-token"] == "andreani-jwt"
    assert response.body == {"ok": True}
    assert client.request_bytes("GET", "https://provider.example.test/label") == b"%PDF-1.4\nlabel"


def test_provider_http_client_types_authentication_failures_without_retry():
    from providers import ProviderAuthenticationError, ProviderHttpClient

    transport = ContractTransport([(401, {}, {"message": "expired"})])

    with pytest.raises(ProviderAuthenticationError):
        ProviderHttpClient(transport, retries=3).request_json(
            "GET", "https://provider.example.test/private"
        )

    assert len(transport.calls) == 1


def test_andreani_uses_official_auth_states_and_pdf_contract():
    from commerce.shipping import AndreaniAdapter, ShippingPolicy

    class TokenCache:
        def __init__(self):
            self.values = {}
            self.set_calls = []

        def get(self, key, default=None):
            return self.values.get(key, default)

        def set(self, key, value, timeout=None):
            self.values[key] = value
            self.set_calls.append((key, value, timeout))

        def delete(self, key):
            self.values.pop(key, None)

    token_cache = TokenCache()

    transport = ContractTransport(
        [
            (200, {"X-Authorization-Token": "andreani-jwt"}, {}),
            (
                200,
                {
                    "pesoAforado": "2.00",
                    "tarifaConIva": {"total": "7041.21"},
                },
            ),
            (
                200,
                {
                    "numeroAndreani": "360000036137650",
                    "estado": "Solicitado",
                    "bultos": [{"numeroDeBulto": "1"}],
                },
            ),
            (200, {"numeroAndreani": "360000036137650", "estado": "Creado"}),
            (200, {"Content-Type": "application/pdf"}, b"%PDF-1.4\nandreani-label"),
            (200, {"numeroAndreani": "360000036137650", "estado": "En distribución"}),
        ]
    )
    adapter = AndreaniAdapter(
        base_url="https://apisqa.andreani.com",
        username="api-user",
        password="api-password",
        customer_id="CL0003750",
        contract="300006611",
        origin={
            "postal_code": "1425",
            "street": "Avenida Santa Fe",
            "number": "3253",
            "city": "Buenos Aires",
            "province": "CABA",
        },
        sender={
            "name": "Mi empresa",
            "email": "envios@example.com",
            "phone": "1122334455",
            "document_type": "CUIT",
            "document_number": "30123456789",
        },
        transport=transport,
        token_cache=token_cache,
    )
    assert adapter.test_connection() is True

    quote = adapter.quote(
        postal_code="1001",
        parcels=[
            {
                "weight_grams": 1500,
                "length_cm": "20",
                "width_cm": "10",
                "height_cm": "5",
            }
        ],
        policy=ShippingPolicy(),
        merchandise_amount=Decimal("25000"),
    )
    imported = adapter.import_shipment(
        {
            "external_id": "ORDER-1-1",
            "recipient": {
                "name": "Ada Compradora",
                "email": "ada@example.test",
                "document_type": "DNI",
                "document_number": "12345678",
                "phone": "1155551234",
            },
            "destination": {
                "postal_code": "1001",
                "street": "Av. de Mayo",
                "number": "1370",
                "city": "Buenos Aires",
                "province": "CABA",
            },
            "parcel": {
                "weight_grams": 1500,
                "length_cm": "20",
                "width_cm": "10",
                "height_cm": "5",
                "declared_value": "25000.00",
            },
        },
        idempotency_key="shipping-idempotency",
    )
    shipment_status = adapter.shipment_status("360000036137650")
    label = adapter.label("360000036137650")
    tracked = adapter.tracking("360000036137650")

    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["url"].endswith("/login")
    assert transport.calls[0]["json"] is None
    assert transport.calls[0]["headers"]["Authorization"] == (
        "Basic " + base64.b64encode(b"api-user:api-password").decode("ascii")
    )
    assert token_cache.set_calls[0][2] == 23 * 60 * 60
    assert transport.calls[1]["url"].endswith("/v1/tarifas")
    assert transport.calls[1]["headers"]["x-authorization-token"] == "andreani-jwt"
    assert transport.calls[1]["params"] == {
        "cpDestino": "1001",
        "contrato": "300006611",
        "cliente": "CL0003750",
        "bultos[0][volumen]": 1000,
        "bultos[0][kilos]": "1.500",
        "bultos[0][altoCm]": "5",
        "bultos[0][largoCm]": "20",
        "bultos[0][anchoCm]": "10",
        "bultos[0][valorDeclarado]": "25000.00",
    }
    assert quote.total_amount == Decimal("7041.21")
    assert quote.service == "andreani_domicilio"
    assert transport.calls[2]["url"].endswith("/v2/ordenes-de-envio")
    assert transport.calls[2]["headers"]["x-authorization-token"] == "andreani-jwt"
    assert transport.calls[2]["headers"]["X-Idempotency-Key"] == "shipping-idempotency"
    assert imported["provider_id"] == "360000036137650"
    assert imported["tracking_number"] == "360000036137650"
    assert imported["state"] == "submitted"
    assert shipment_status["state"] == "created"
    assert label == b"%PDF-1.4\nandreani-label"
    assert tracked["estado"] == "En distribución"


def test_andreani_refreshes_an_expired_token_once():
    from commerce.shipping import AndreaniAdapter, ShippingPolicy

    class TokenCache:
        value = ""

        def get(self, key, default=None):
            del key
            return self.value or default

        def set(self, key, value, timeout=None):
            del key, timeout
            self.value = value

        def delete(self, key):
            del key
            self.value = ""

    transport = ContractTransport(
        [
            (200, {"x-authorization-token": "expired-token"}, {}),
            (401, {}, {"message": "expired"}),
            (200, {"x-authorization-token": "fresh-token"}, {}),
            (200, {"tarifaConIva": {"total": "1000.00"}}),
        ]
    )
    adapter = AndreaniAdapter(
        base_url="https://apisqa.andreani.com",
        username="refresh-user",
        password="refresh-password",
        customer_id="CL0003750",
        contract="300006611",
        origin={
            "postal_code": "1425",
            "street": "Avenida Santa Fe",
            "number": "3253",
            "city": "Buenos Aires",
        },
        sender={
            "name": "Mi empresa",
            "email": "envios@example.com",
            "phone": "1122334455",
            "document_type": "CUIT",
            "document_number": "30123456789",
        },
        transport=transport,
        token_cache=TokenCache(),
    )

    quote = adapter.quote(
        postal_code="1001",
        parcels=[
            {
                "weight_grams": 1000,
                "length_cm": "10",
                "width_cm": "10",
                "height_cm": "10",
            }
        ],
        policy=ShippingPolicy(),
        merchandise_amount=Decimal("10000"),
    )

    assert quote.total_amount == Decimal("1000.00")
    assert [call["url"] for call in transport.calls].count(
        "https://apisqa.andreani.com/login"
    ) == 2
    assert transport.calls[-1]["headers"]["x-authorization-token"] == "fresh-token"


def test_andreani_rejects_unknown_pre_shipment_states():
    from commerce.shipping import AndreaniAdapter
    from providers import ProviderInvalidResponse

    adapter = object.__new__(AndreaniAdapter)

    with pytest.raises(ProviderInvalidResponse):
        adapter._normalize_order(
            {"numeroAndreani": "360000036137650", "estado": "Estado inesperado"}
        )


@pytest.mark.django_db
def test_no_configured_carrier_creates_explicit_manual_quote(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.shipping import create_shipping_quote_options
    from locations.models import Address

    user = django_user_model.objects.create_user(email="manual-quote@example.test")
    cart = Cart.objects.create(user=user)
    variant = make_variant(sku="MANUAL-QUOTE", price="12000", on_hand=4)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    address = Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. de Mayo 1370",
        street="Av. de Mayo",
        number="1370",
        postal_code="1001",
        locality="Buenos Aires",
        province="CABA",
        needs_review=False,
    )

    options = create_shipping_quote_options(
        cart=cart,
        user=user,
        address=address,
        bindings=[],
    )

    assert options.manual_fallback is True
    assert len(options.quotes) == 1
    assert options.quotes[0].provider == "manual"
    assert options.quotes[0].service == "a_convenir"
    assert options.quotes[0].amount_pending is True
    assert options.quotes[0].total_amount == Decimal("0.00")
    assert options.quotes[0].parcels == []


@pytest.mark.django_db
def test_configured_provider_failure_does_not_silently_become_manual(django_user_model):
    from commerce.models import Cart, CartLine, PackageBox
    from commerce.shipping import CarrierBinding, ShippingPolicy, create_shipping_quote_options
    from locations.models import Address
    from providers import ProviderUnavailable

    class DownCarrier:
        provider = "andreani"

        def quote(self, **kwargs):
            del kwargs
            raise ProviderUnavailable("Andreani no responde")

    user = django_user_model.objects.create_user(email="down-carrier@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart,
        variant=make_variant(sku="DOWN-CARRIER", price="15000", on_hand=4),
        quantity=1,
    )
    PackageBox.objects.create(
        code="down-box",
        inner_length_cm="30",
        inner_width_cm="20",
        inner_height_cm="10",
        tare_weight_grams=100,
        max_weight_grams=5000,
    )
    address = Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. de Mayo 1370",
        street="Av. de Mayo",
        number="1370",
        postal_code="1001",
        locality="Buenos Aires",
        province="CABA",
        needs_review=False,
    )

    with pytest.raises(ProviderUnavailable):
        create_shipping_quote_options(
            cart=cart,
            user=user,
            address=address,
            bindings=[
                CarrierBinding(
                    provider="andreani",
                    label="Andreani",
                    adapter=DownCarrier(),
                    policy=ShippingPolicy(),
                )
            ],
        )


@pytest.mark.django_db
def test_manual_shipping_waits_for_admin_cost_then_resumes_one_combined_payment(
    django_user_model,
):
    from accounts.models import BillingProfile
    from commerce.checkout import confirm_checkout, resume_checkout
    from commerce.models import Cart, CartLine, ShippingQuote
    from commerce.shipping import resolve_manual_shipping_cost
    from locations.models import Address

    user = django_user_model.objects.create_user(
        email="manual-checkout@example.test", email_verified_at=timezone.now()
    )
    make_customer(user)
    billing = BillingProfile.objects.create(
        customer=user.customer_profile,
        label="Consumidor final",
        legal_name="Ada Compradora",
        tax_condition="consumidor_final",
    )
    billing.set_cuit("20-12345678-6")
    billing.save()
    cart = Cart.objects.create(user=user)
    variant = make_variant(sku="MANUAL-CHECKOUT", price="12000", on_hand=4)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    address = Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. de Mayo 1370",
        street="Av. de Mayo",
        number="1370",
        postal_code="1001",
        locality="Buenos Aires",
        province="CABA",
        needs_review=False,
    )
    quote = ShippingQuote.objects.create(
        user=user,
        provider="manual",
        service="a_convenir",
        postal_code="1001",
        parcels=[],
        base_amount="0",
        surcharge_amount="0",
        total_amount="0",
        amount_pending=True,
        cart_fingerprint="placeholder",
        provider_summary={"label": "Envío a acordar"},
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    from commerce.checkout import cart_fingerprint

    quote.cart_fingerprint = cart_fingerprint(cart, address=address, parcels=[])
    quote.save(update_fields=("cart_fingerprint",))

    class RecordingPayment(PreferencePayment):
        collector_id = ""
        calls = []

        def create_preference(self, **kwargs):
            self.calls.append(kwargs)
            return super().create_preference(**kwargs)

    payment = RecordingPayment()
    result = confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method="shipping",
        sid_adapter=ApprovedSID(),
        payment_adapter=payment,
        address=address,
        shipping_quote=quote,
        billing_profile=billing,
        consent=True,
        idempotency_key=uuid.uuid4(),
    )

    assert result.checkout_url == ""
    assert result.transaction is None
    assert result.order.shipping_cost_status == "pending_agreement"
    assert result.order.payment_status == "not_started"
    assert result.order.reservations.count() == 0
    assert payment.calls == []

    operator = django_user_model.objects.create_superuser(
        email="shipping-operator@example.test", password="test"
    )
    resolved = resolve_manual_shipping_cost(
        order=result.order,
        amount=Decimal("2500.00"),
        actor=operator,
        reason="Costo confirmado con el cliente",
    )
    assert resolved.shipping_cost_status == "ready"
    assert resolved.shipping_amount_snapshot == Decimal("2500.00")
    assert resolved.total_snapshot == Decimal("14500.00")

    from commerce.serializers import CartSerializer

    active_checkout = CartSerializer(cart).data["active_checkout"]
    assert active_checkout == {
        "order_id": str(resolved.public_id),
        "identity_status": "verified",
        "payment_status": "not_started",
        "shipping_cost_status": "ready",
        "shipping_amount": "2500.00",
        "total": "14500.00",
        "can_resume": True,
    }

    resumed = resume_checkout(
        order=resolved,
        cart=cart,
        user=user,
        payment_adapter=payment,
    )
    assert resumed.checkout_url
    assert resumed.transaction.amount == Decimal("14500.00")
    assert payment.calls[-1]["amount"] == Decimal("14500.00")


def test_management_definitions_name_micorreo_and_expose_andreani():
    from backoffice.integrations import INTEGRATION_DEFINITIONS

    assert INTEGRATION_DEFINITIONS["correo_argentino"].label == "API MiCorreo"
    assert INTEGRATION_DEFINITIONS["andreani"].label == "Andreani"
    assert {"customer_id", "contract", "origin_postal_code"} <= set(
        INTEGRATION_DEFINITIONS["andreani"].required_public
    )
    assert INTEGRATION_DEFINITIONS["andreani"].required_secrets == (
        "username",
        "password",
    )


@pytest.mark.django_db
def test_plural_shipping_quotes_api_returns_manual_option_only_when_none_configured(
    django_user_model,
):
    from rest_framework.test import APIClient

    from commerce.models import Cart, CartLine
    from locations.models import Address

    user = django_user_model.objects.create_user(
        email="shipping-options-api@example.test", email_verified_at=timezone.now()
    )
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart,
        variant=make_variant(sku="OPTIONS-API", price="18000", on_hand=3),
        quantity=1,
    )
    address = Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. de Mayo 1370",
        street="Av. de Mayo",
        number="1370",
        postal_code="1001",
        locality="Buenos Aires",
        province="CABA",
        needs_review=False,
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1/shipping/quotes/", {"address_id": address.pk}, format="json"
    )

    assert response.status_code == 200
    assert response.data["manual_fallback"] is True
    assert response.data["errors"] == []
    assert response.data["results"][0]["provider"] == "manual"
    assert response.data["results"][0]["provider_label"] == "Envío a acordar"
    assert response.data["results"][0]["amount_pending"] is True
    assert response.data["results"][0]["parcels"] == []


@pytest.mark.django_db
def test_management_can_set_manual_shipping_cost_through_order_action(django_user_model):
    from rest_framework.test import APIClient

    from commerce.models import Cart, CartLine, ShippingQuote
    from commerce.services import create_pending_identity_order
    from locations.models import Address

    user = django_user_model.objects.create_user(email="manual-action@example.test")
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(
        cart=cart,
        variant=make_variant(sku="MANUAL-ACTION", price="10000", on_hand=3),
        quantity=1,
    )
    address = Address.objects.create(
        user=user,
        label="Casa",
        raw_address="Av. de Mayo 1370",
        street="Av. de Mayo",
        number="1370",
        postal_code="1001",
        locality="Buenos Aires",
        province="CABA",
        needs_review=False,
    )
    from commerce.checkout import cart_fingerprint

    quote = ShippingQuote.objects.create(
        user=user,
        provider="manual",
        service="a_convenir",
        postal_code="1001",
        parcels=[],
        base_amount="0",
        total_amount="0",
        amount_pending=True,
        cart_fingerprint=cart_fingerprint(cart, address=address, parcels=[]),
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email, "name": "Ada"},
        address_snapshot={
            "street": address.street,
            "number": address.number,
            "postal_code": address.postal_code,
            "locality": address.locality,
            "province": address.province,
        },
        fiscal_snapshot={},
        fulfillment_method="shipping",
        shipping_quote=quote,
    )
    operator = django_user_model.objects.create_superuser(
        email="manual-action-operator@example.test", password="test"
    )
    client = APIClient()
    client.force_authenticate(operator)

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {
            "action": "set_shipping_cost",
            "reason": "Costo confirmado por teléfono",
            "shipping_amount": "2300.00",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["shipping_cost_status"] == "ready"
    assert response.data["shipping_amount"] == "2300.00"
    assert response.data["total"] == "12300.00"
