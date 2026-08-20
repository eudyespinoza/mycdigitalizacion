import os

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
