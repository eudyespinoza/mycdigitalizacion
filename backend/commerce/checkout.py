from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from commerce.identity_service import validate_identity
from commerce.models import Cart, PaymentTransaction, ShippingQuote
from commerce.services import (
    InsufficientStock,
    create_pending_identity_order,
    create_reservation,
    transition_order_status,
)
from commerce.shipping import quote_is_valid


class CheckoutError(ValueError):
    def __init__(self, code, message, *, diagnostics=""):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class CheckoutResult:
    order: object
    transaction: PaymentTransaction | None
    checkout_url: str


def cart_fingerprint(cart):
    rows = list(cart.lines.order_by("variant_id").values_list("variant_id", "quantity"))
    raw = json.dumps(rows, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _validate_shipping(*, user, cart, fulfillment_method, address, shipping_quote, now):
    if fulfillment_method == "pickup":
        return None
    if fulfillment_method != "shipping":
        raise CheckoutError("invalid_fulfillment", "Elegí una forma de entrega válida")
    if address is None or address.user_id != user.pk:
        raise CheckoutError("address_required", "Elegí una dirección de entrega válida")
    if address.needs_review:
        raise CheckoutError("address_review_required", "Confirmá la ubicación de entrega")
    if not isinstance(shipping_quote, ShippingQuote) or shipping_quote.user_id != user.pk:
        raise CheckoutError("shipping_quote_required", "Necesitamos volver a cotizar el envío")
    if not quote_is_valid(shipping_quote.expires_at, now=now):
        raise CheckoutError("shipping_quote_expired", "La cotización de envío venció")
    if shipping_quote.cart_fingerprint != cart_fingerprint(cart):
        raise CheckoutError("shipping_quote_changed", "El carrito cambió desde la cotización")
    if shipping_quote.postal_code != address.postal_code:
        raise CheckoutError("shipping_quote_changed", "La dirección cambió desde la cotización")
    return shipping_quote


def confirm_checkout(
    *,
    cart,
    user,
    fulfillment_method,
    sid_adapter,
    payment_adapter,
    address=None,
    shipping_quote=None,
):
    if cart.user_id != user.pk:
        raise CheckoutError("cart_owner_mismatch", "No encontramos ese carrito")
    try:
        validate_email(user.email)
    except ValidationError as exc:
        raise CheckoutError("invalid_email", "Revisá tu correo electrónico") from exc
    if not user.email_verified_at:
        raise CheckoutError("email_not_verified", "Verificá tu correo electrónico")
    try:
        customer = user.customer_profile
    except Exception as exc:
        raise CheckoutError("identity_missing", "Completá tus datos de identidad") from exc
    if not customer.get_dni():
        raise CheckoutError("identity_missing", "Completá tus datos de identidad")
    identity = validate_identity(customer=customer, adapter=sid_adapter, consent=True)
    now = timezone.now()

    try:
        with transaction.atomic():
            locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
            try:
                validate_email(locked_user.email)
            except ValidationError as exc:
                raise CheckoutError("invalid_email", "Revisá tu correo electrónico") from exc
            if not locked_user.email_verified_at:
                raise CheckoutError("email_not_verified", "Verificá tu correo electrónico")
            locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
            locked_address = (
                type(address).objects.select_for_update().get(pk=address.pk)
                if address is not None
                else None
            )
            locked_quote = (
                ShippingQuote.objects.select_for_update().get(pk=shipping_quote.pk)
                if shipping_quote is not None
                else None
            )
            lines = list(locked_cart.lines.select_for_update().select_related("variant__product"))
            if not lines:
                raise CheckoutError("empty_cart", "El carrito está vacío")
            effective_quote = _validate_shipping(
                user=user,
                cart=locked_cart,
                fulfillment_method=fulfillment_method,
                address=locked_address,
                shipping_quote=locked_quote,
                now=now,
            )
            order = create_pending_identity_order(
                cart=locked_cart,
                customer_snapshot={
                    "email": user.email,
                    "document": identity.masked_audit.get("document", ""),
                },
                address_snapshot=(
                    {
                        "street": locked_address.street,
                        "number": locked_address.number,
                        "postal_code": locked_address.postal_code,
                        "locality": locked_address.locality,
                        "province": locked_address.province,
                        "floor": locked_address.floor,
                        "apartment": locked_address.apartment,
                        "reference": locked_address.reference,
                    }
                    if locked_address
                    else {}
                ),
                fiscal_snapshot={},
                fulfillment_method=fulfillment_method,
                shipping_quote=effective_quote,
                at=now,
            )
            if identity.status == identity.Status.PENDING_REVIEW:
                return CheckoutResult(order, None, "")
            transition_order_status(
                order=order, field="identity_status", value=order.IdentityStatus.VERIFIED
            )
            expiry = now + timezone.timedelta(minutes=20)
            for line in lines:
                reservation = create_reservation(
                    variant=line.variant,
                    quantity=line.quantity,
                    reference=str(order.public_id),
                    expires_at=expiry,
                )
                order.reservations.add(reservation)
            payment_transaction = PaymentTransaction.objects.create(
                order=order,
                external_reference=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                amount=order.total_snapshot,
                currency="ARS",
                expected_collector_id=getattr(payment_adapter, "collector_id", ""),
                live_mode=bool(getattr(payment_adapter, "live_mode", False)),
            )
            preference = payment_adapter.create_preference(
                external_reference=str(payment_transaction.external_reference),
                amount=payment_transaction.amount,
                description=f"Pedido {order.public_id}",
                payer_email=user.email,
                idempotency_key=str(payment_transaction.idempotency_key),
                now=now,
            )
            payment_transaction.preference_id = preference.preference_id
            payment_transaction.checkout_url = preference.checkout_url
            payment_transaction.save(update_fields=("preference_id", "checkout_url", "updated_at"))
            transition_order_status(
                order=order, field="payment_status", value=order.PaymentStatus.PENDING
            )
            return CheckoutResult(order, payment_transaction, preference.checkout_url)
    except InsufficientStock as exc:
        raise CheckoutError("insufficient_stock", "No hay stock suficiente") from exc


def resume_checkout(*, order, cart, user, payment_adapter):
    identity = user.identity_verifications.filter(status="approved").order_by("-created_at").first()
    if not identity:
        raise CheckoutError("identity_pending_review", "La identidad todavía está en revisión")

    # Resuming deliberately goes through confirmation again, so price, promotion,
    # quote and stock checks are not inherited from the earlier snapshot.
    class Approved:
        def verify(self, *, dni, consent):
            from commerce.identity import SIDResult

            return SIDResult("approved", identity.provider_reference or "manual", {})

    address = None
    if order.fulfillment_method == order.FulfillmentMethod.SHIPPING:
        address = user.addresses.filter(
            street=order.address_snapshot.get("street", ""),
            number=order.address_snapshot.get("number", ""),
            postal_code=order.address_snapshot.get("postal_code", ""),
        ).first()

    return confirm_checkout(
        cart=cart,
        user=user,
        fulfillment_method=order.fulfillment_method,
        sid_adapter=Approved(),
        payment_adapter=payment_adapter,
        address=address,
        shipping_quote=order.shipping_quote,
    )
