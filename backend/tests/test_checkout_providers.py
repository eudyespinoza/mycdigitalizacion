from decimal import Decimal

import pytest
from django.utils import timezone


def test_postal_code_normalization_accepts_cp4_and_cpa8():
    from locations.services import normalize_postal_code

    assert normalize_postal_code(" 1414 ") == "1414"
    assert normalize_postal_code("c1414abc") == "C1414ABC"
    with pytest.raises(ValueError, match="CP4 or CPA8"):
        normalize_postal_code("141")


def test_georef_geocode_payload_excludes_private_address_details():
    from locations.providers import GeoRefAdapter

    transport = RecordingTransport(
        {
            "direcciones": [
                {
                    "nomenclatura": "AV RIVADAVIA 1234, CABA",
                    "ubicacion": {"lat": -34.6, "lon": -58.4},
                }
            ]
        }
    )
    result = GeoRefAdapter(transport=transport).geocode(
        street="Av Rivadavia",
        number="1234",
        locality="CABA",
        province="CABA",
        floor="9",
        apartment="B",
        notes="timbre secreto",
    )

    sent = transport.calls[0][3]
    assert sent == {
        "direccion": "Av Rivadavia 1234",
        "localidad": "CABA",
        "provincia": "CABA",
        "max": 1,
    }
    assert result.normalized_address == "AV RIVADAVIA 1234, CABA"


def test_georef_geocode_falls_back_to_locality_center_when_address_has_no_match():
    from locations.providers import GeoRefAdapter

    transport = SequenceTransport(
        [
            (200, {"cantidad": 0, "direcciones": []}),
            (
                200,
                {
                    "cantidad": 1,
                    "localidades": [
                        {
                            "id": "30084160",
                            "nombre": "Paraná",
                            "centroide": {
                                "lat": -31.7401601621031,
                                "lon": -60.5274260494443,
                            },
                            "provincia": {"id": "30", "nombre": "Entre Ríos"},
                        }
                    ],
                },
            ),
        ]
    )

    result = GeoRefAdapter(transport=transport).geocode(
        street="Ayacucho",
        number="982",
        locality="Paraná",
        province="Entre Ríos",
    )

    assert result.normalized_address == "Ayacucho 982, Paraná, Entre Ríos"
    assert result.latitude == Decimal("-31.7401601621031")
    assert result.longitude == Decimal("-60.5274260494443")
    assert result.confidence is None
    assert result.summary == {
        "province_id": "30",
        "locality_id": "30084160",
        "precision": "locality",
    }


def test_distance_helper_uses_150_meter_boundary():
    from locations.services import is_within_distance

    assert is_within_distance(-34.6037, -58.3816, -34.60236, -58.3816, 150)
    assert not is_within_distance(-34.6037, -58.3816, -34.60230, -58.3816, 150)


def test_packing_rotates_products_and_uses_smallest_box():
    from commerce.packing import Box, PackItem, pack_items

    result = pack_items(
        [PackItem("ROTATED", Decimal("8"), Decimal("4"), Decimal("6"), 900, 1)],
        [
            Box("large", Decimal("12"), Decimal("12"), Decimal("12"), 200, 3000),
            Box("small", Decimal("6"), Decimal("8"), Decimal("4"), 100, 1500),
        ],
    )

    assert result.success is True
    assert [(parcel.box_code, parcel.total_weight_grams) for parcel in result.parcels] == [
        ("small", 1000)
    ]


def test_packing_splits_multiple_boxes_and_reports_failure():
    from commerce.packing import Box, PackItem, pack_items

    box = Box("one", Decimal("10"), Decimal("10"), Decimal("10"), 100, 1200)
    split = pack_items(
        [PackItem("SKU", Decimal("10"), Decimal("10"), Decimal("10"), 1000, 2)],
        [box],
    )
    impossible = pack_items(
        [PackItem("TOO-BIG", Decimal("11"), Decimal("10"), Decimal("10"), 100, 1)],
        [box],
    )

    assert [parcel.total_weight_grams for parcel in split.parcels] == [1100, 1100]
    assert impossible.success is False
    assert impossible.reason == "cannot_pack"


def test_packing_combines_units_when_they_share_a_box_safely():
    from commerce.packing import Box, PackItem, pack_items

    result = pack_items(
        [PackItem("HALF", Decimal("5"), Decimal("10"), Decimal("10"), 400, 2)],
        [Box("combined", Decimal("10"), Decimal("10"), Decimal("10"), 100, 1500)],
    )

    assert result.success is True
    assert [(parcel.item_skus, parcel.total_weight_grams) for parcel in result.parcels] == [
        (("HALF", "HALF"), 900)
    ]


def test_shipping_quote_expiry_is_strict():
    from commerce.shipping import quote_is_valid

    now = timezone.now()
    assert quote_is_valid(now + timezone.timedelta(seconds=1), now=now)
    assert not quote_is_valid(now, now=now)


class RecordingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        self.calls.append((method, url, headers, params or json, timeout))
        return 200, self.response


def test_sid_disabled_unavailable_and_rejected_are_typed():
    from commerce.identity import DisabledSIDAdapter, SIDAdapter
    from providers import ProviderNotConfigured, ProviderRejected, ProviderUnavailable

    with pytest.raises(ProviderNotConfigured):
        DisabledSIDAdapter().verify(dni="12345678", consent=True)

    unavailable = RecordingTransport({})
    unavailable.response = (503, {})
    with pytest.raises(ProviderUnavailable):
        SIDAdapter(
            base_url="https://sid.example.test", token="token", transport=TupleTransport(503, {})
        ).verify(dni="12345678", consent=True)

    rejected = SIDAdapter(
        base_url="https://sid.example.test",
        token="token",
        transport=TupleTransport(200, {"status": "rejected", "reference": "sid-1"}),
    )
    with pytest.raises(ProviderRejected):
        rejected.verify(dni="12345678", consent=True)


def test_correo_aggregates_parcel_rates_and_applies_surcharge():
    from commerce.shipping import CorreoArgentinoAdapter, ShippingPolicy

    adapter = CorreoArgentinoAdapter(
        base_url="https://correo.example.test",
        username="user",
        password="pass",
        customer_id="customer",
        origin_postal_code="1000",
        transport=SequenceTransport(
            [
                (200, {"token": "carrier-token"}),
                (
                    200,
                    {
                        "rates": [
                            {"deliveredType": "D", "price": "100.00", "productType": "CP"}
                        ]
                    },
                ),
                (
                    200,
                    {
                        "rates": [
                            {"deliveredType": "D", "price": "50.00", "productType": "CP"}
                        ]
                    },
                ),
            ]
        ),
    )
    quote = adapter.quote(
        postal_code="1414",
        parcels=[
            {"weight_grams": 1000, "length_cm": 10, "width_cm": 10, "height_cm": 10},
            {"weight_grams": 500, "length_cm": 10, "width_cm": 10, "height_cm": 10},
        ],
        policy=ShippingPolicy(surcharge_type="percentage", surcharge_value=Decimal("10")),
    )

    assert quote.base_amount == Decimal("150.00")
    assert quote.surcharge_amount == Decimal("15.00")
    assert quote.total_amount == Decimal("165.00")


def test_mercadopago_preference_is_ars_expiring_and_idempotent():
    from commerce.mercadopago import MercadoPagoAdapter

    now = timezone.now()
    transport = TupleTransport(
        201,
        {"id": "pref-1", "init_point": "https://mercadopago.com/checkout/pref-1"},
    )
    preference = MercadoPagoAdapter(
        access_token="secret-token",
        webhook_secret="webhook-secret",
        back_url_base="https://shop.example.test",
        transport=transport,
        live_mode=True,
    ).create_preference(
        external_reference="8c28ebaf-3b83-47be-9ddb-ec1c054f46df",
        order_id="27539126-0d2d-4a7e-af10-dc959160328c",
        amount=Decimal("123.45"),
        description="Pedido 123",
        payer_email="buyer@example.test",
        idempotency_key="idem-1",
        now=now,
    )

    headers = transport.calls[0][2]
    payload = transport.calls[0][3]
    assert headers["X-Idempotency-Key"] == "idem-1"
    assert "secret-token" not in str(transport.calls)
    assert payload["items"] == [
        {"title": "Pedido 123", "quantity": 1, "currency_id": "ARS", "unit_price": 123.45}
    ]
    assert payload["expiration_date_to"] == (now + timezone.timedelta(minutes=20)).isoformat()
    assert all(url.startswith("https://") for url in payload["back_urls"].values())
    assert preference.preference_id == "pref-1"


def test_webhook_signature_rejects_stale_timestamp_and_accepts_valid_hmac():
    import hashlib
    import hmac

    from commerce.payments import validate_webhook_signature

    now = timezone.now()
    timestamp = str(int(now.timestamp()))
    manifest = f"id:42;request-id:req-1;ts:{timestamp};"
    signature = hmac.new(b"secret", manifest.encode(), hashlib.sha256).hexdigest()
    header = f"ts={timestamp},v1={signature}"

    assert validate_webhook_signature(
        data_id="42", request_id="req-1", signature_header=header, secret="secret", now=now
    )
    assert not validate_webhook_signature(
        data_id="42",
        request_id="req-1",
        signature_header=header,
        secret="secret",
        now=now + timezone.timedelta(minutes=10),
    )


class TupleTransport:
    def __init__(self, status, response):
        self.status = status
        self.response = response
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        safe_headers = {
            key: ("***" if key.lower() == "authorization" else value)
            for key, value in (headers or {}).items()
        }
        self.calls.append((method, url, safe_headers, json or params, timeout))
        return self.status, self.response


class SequenceTransport:
    def __init__(self, responses):
        self.responses = iter(responses)

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        return next(self.responses)
