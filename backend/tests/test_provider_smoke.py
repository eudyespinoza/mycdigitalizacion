import os
from decimal import Decimal

import pytest


@pytest.mark.sandbox
@pytest.mark.skipif(not os.getenv("MERCADOPAGO_ACCESS_TOKEN"), reason="sandbox credentials absent")
def test_mercadopago_sandbox_payment_fetch_smoke():
    from django.conf import settings

    from commerce.mercadopago import MercadoPagoAdapter

    payment_id = os.environ["MERCADOPAGO_SANDBOX_PAYMENT_ID"]
    adapter = MercadoPagoAdapter(
        access_token=settings.MERCADOPAGO_ACCESS_TOKEN,
        webhook_secret=settings.MERCADOPAGO_WEBHOOK_SECRET,
        back_url_base=settings.PUBLIC_BACKEND_URL,
    )
    assert adapter.fetch_payment(payment_id)["id"]


ANDREANI_QA_VARIABLES = (
    "ANDREANI_QA_USERNAME",
    "ANDREANI_QA_PASSWORD",
    "ANDREANI_QA_CUSTOMER_ID",
    "ANDREANI_QA_CONTRACT",
    "ANDREANI_QA_ORIGIN_POSTAL_CODE",
    "ANDREANI_QA_ORIGIN_STREET",
    "ANDREANI_QA_ORIGIN_NUMBER",
    "ANDREANI_QA_ORIGIN_CITY",
    "ANDREANI_QA_SENDER_NAME",
    "ANDREANI_QA_SENDER_EMAIL",
    "ANDREANI_QA_SENDER_PHONE",
    "ANDREANI_QA_SENDER_DOCUMENT_TYPE",
    "ANDREANI_QA_SENDER_DOCUMENT_NUMBER",
    "ANDREANI_QA_DESTINATION_POSTAL_CODE",
)


@pytest.mark.sandbox
@pytest.mark.skipif(
    not all(os.getenv(name) for name in ANDREANI_QA_VARIABLES),
    reason="Andreani QA credentials absent",
)
def test_andreani_qa_login_and_quote_smoke():
    from commerce.shipping import AndreaniAdapter, ShippingPolicy

    adapter = AndreaniAdapter(
        base_url="https://apisqa.andreani.com",
        username=os.environ["ANDREANI_QA_USERNAME"],
        password=os.environ["ANDREANI_QA_PASSWORD"],
        customer_id=os.environ["ANDREANI_QA_CUSTOMER_ID"],
        contract=os.environ["ANDREANI_QA_CONTRACT"],
        origin={
            "postal_code": os.environ["ANDREANI_QA_ORIGIN_POSTAL_CODE"],
            "street": os.environ["ANDREANI_QA_ORIGIN_STREET"],
            "number": os.environ["ANDREANI_QA_ORIGIN_NUMBER"],
            "city": os.environ["ANDREANI_QA_ORIGIN_CITY"],
        },
        sender={
            "name": os.environ["ANDREANI_QA_SENDER_NAME"],
            "email": os.environ["ANDREANI_QA_SENDER_EMAIL"],
            "phone": os.environ["ANDREANI_QA_SENDER_PHONE"],
            "document_type": os.environ["ANDREANI_QA_SENDER_DOCUMENT_TYPE"],
            "document_number": os.environ["ANDREANI_QA_SENDER_DOCUMENT_NUMBER"],
        },
    )

    assert adapter.test_connection() is True
    quote = adapter.quote(
        postal_code=os.environ["ANDREANI_QA_DESTINATION_POSTAL_CODE"],
        parcels=[
            {
                "weight_grams": 1000,
                "length_cm": "20",
                "width_cm": "15",
                "height_cm": "10",
            }
        ],
        policy=ShippingPolicy(),
        merchandise_amount=Decimal("10000.00"),
    )
    assert quote.total_amount >= Decimal("0.00")
