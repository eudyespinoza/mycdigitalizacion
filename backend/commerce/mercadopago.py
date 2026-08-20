from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from providers import (
    ProviderHttpClient,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    UrllibJsonTransport,
)


@dataclass(frozen=True)
class CheckoutPreference:
    preference_id: str
    checkout_url: str
    expires_at: object


class MercadoPagoAdapter:
    base_url = "https://api.mercadopago.com"

    def __init__(
        self,
        *,
        access_token,
        webhook_secret,
        back_url_base,
        transport=None,
        live_mode=False,
    ):
        if not access_token or not webhook_secret:
            raise ProviderNotConfigured("Mercado Pago no está configurado")
        parsed = urlsplit(back_url_base)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderNotConfigured("Mercado Pago requiere URLs públicas HTTPS")
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.back_url_base = back_url_base.rstrip("/")
        self.live_mode = bool(live_mode)
        self.http = ProviderHttpClient(transport or UrllibJsonTransport())

    def _headers(self, *, idempotency_key=None):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    def create_preference(
        self,
        *,
        external_reference,
        amount,
        description,
        payer_email,
        idempotency_key,
        now,
    ):
        try:
            uuid.UUID(str(external_reference))
        except ValueError as exc:
            raise ValueError("external_reference must be a UUID") from exc
        expires_at = now + timedelta(minutes=20)
        return_url = f"{self.back_url_base}/checkout/payment-status/{external_reference}"
        payload = {
            "items": [
                {
                    "title": description,
                    "quantity": 1,
                    "currency_id": "ARS",
                    "unit_price": float(Decimal(amount)),
                }
            ],
            "payer": {"email": payer_email},
            "external_reference": str(external_reference),
            "notification_url": f"{self.back_url_base}/api/v1/payments/mercadopago/webhook/",
            "back_urls": {
                "success": return_url,
                "pending": return_url,
                "failure": return_url,
            },
            "auto_return": "approved",
            "expires": True,
            "expiration_date_to": expires_at.isoformat(),
        }
        data = self.http.request_json(
            "POST",
            f"{self.base_url}/checkout/preferences",
            headers=self._headers(idempotency_key=idempotency_key),
            payload=payload,
            idempotent=True,
            expected=(200, 201),
        )
        preference_id = str(data.get("id", ""))
        checkout_url = str(
            data.get("init_point" if self.live_mode else "sandbox_init_point")
            or data.get("init_point")
            or data.get("sandbox_init_point")
            or ""
        )
        if not preference_id or not checkout_url:
            raise ProviderInvalidResponse("Mercado Pago no devolvió una preferencia de pago válida")
        return CheckoutPreference(preference_id, checkout_url, expires_at)

    def fetch_payment(self, payment_id):
        return self.http.request_json(
            "GET", f"{self.base_url}/v1/payments/{payment_id}", headers=self._headers()
        )

    def refund(self, payment_id, *, amount=None, idempotency_key):
        payload = {} if amount is None else {"amount": float(Decimal(amount))}
        return self.http.request_json(
            "POST",
            f"{self.base_url}/v1/payments/{payment_id}/refunds",
            headers=self._headers(idempotency_key=idempotency_key),
            payload=payload,
            idempotent=True,
            expected=(200, 201),
        )
