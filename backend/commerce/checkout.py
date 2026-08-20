from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import BillingProfile
from commerce.identity_service import validate_identity
from commerce.models import Cart, PaymentTransaction, ShippingQuote
from commerce.services import (
    InsufficientStock,
    calculate_cart_totals,
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


def _fiscal_snapshot(profile):
    return {
        "profile_id": profile.pk,
        "label": profile.label,
        "legal_name": profile.legal_name,
        "tax_condition": profile.tax_condition,
        "cuit_encrypted": profile.cuit_encrypted,
        "cuit_hash": profile.cuit_hash,
        "masked_cuit": profile.masked_cuit,
    }


def cart_fingerprint(cart, *, address=None, parcels=None, at=None):
    checked_at = at or timezone.now()
    rows = []
    for line in cart.lines.select_related("variant").order_by("variant_id"):
        variant = line.variant
        rows.append(
            {
                "variant_id": variant.pk,
                "quantity": line.quantity,
                "price": str(variant.price),
                "dimensions": [
                    str(variant.length_cm),
                    str(variant.width_cm),
                    str(variant.height_cm),
                ],
                "weight_grams": variant.packaged_weight_grams,
            }
        )
    totals = calculate_cart_totals(cart, at=checked_at)
    payload = {
        "lines": rows,
        "coupon": cart.coupon.code if cart.coupon_id else "",
        "totals": [str(totals.subtotal), str(totals.discount), str(totals.total)],
        "address": (
            {
                field: getattr(address, field)
                for field in ("street", "number", "postal_code", "locality", "province")
            }
            if address is not None
            else None
        ),
        "parcels": parcels or [],
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
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
    if shipping_quote.cart_fingerprint != cart_fingerprint(
        cart, address=address, parcels=shipping_quote.parcels, at=now
    ):
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
    billing_profile=None,
    consent=None,
    idempotency_key=None,
):
    if cart.user_id != user.pk:
        raise CheckoutError("cart_owner_mismatch", "No encontramos ese carrito")
    try:
        validate_email(user.email)
    except ValidationError as exc:
        raise CheckoutError("invalid_email", "Revisá tu correo electrónico") from exc
    if not user.email_verified_at:
        raise CheckoutError("email_not_verified", "Verificá tu correo electrónico")
    if consent is not True:
        raise CheckoutError(
            "identity_consent_required", "Necesitamos tu consentimiento para validar la identidad"
        )
    if idempotency_key is None:
        idempotency_key = uuid.uuid4()
    existing_order = user.orders.filter(checkout_idempotency_key=idempotency_key).first()
    if existing_order:
        existing_transaction = existing_order.payment_transactions.order_by("created_at").first()
        return CheckoutResult(
            existing_order,
            existing_transaction,
            existing_transaction.checkout_url if existing_transaction else "",
        )
    try:
        customer = user.customer_profile
    except Exception as exc:
        raise CheckoutError("identity_missing", "Completá tus datos de identidad") from exc
    if not customer.get_dni():
        raise CheckoutError("identity_missing", "Completá tus datos de identidad")
    if billing_profile is None or billing_profile.customer_id != customer.pk:
        raise CheckoutError("billing_profile_invalid", "Elegí un perfil fiscal válido")
    identity = validate_identity(customer=customer, adapter=sid_adapter, consent=consent)
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
            locked_billing_profile = (
                BillingProfile.objects.select_for_update()
                .filter(pk=billing_profile.pk, customer__user=locked_user)
                .first()
            )
            if not locked_billing_profile:
                raise CheckoutError("billing_profile_invalid", "Elegí un perfil fiscal válido")
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
                    "name": (
                        f"{locked_user.profile.first_name} {locked_user.profile.last_name}".strip()
                        if hasattr(locked_user, "profile")
                        else ""
                    ),
                    "phone": locked_user.profile.phone if hasattr(locked_user, "profile") else "",
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
                fiscal_snapshot=_fiscal_snapshot(locked_billing_profile),
                fulfillment_method=fulfillment_method,
                shipping_quote=effective_quote,
                checkout_idempotency_key=idempotency_key,
                at=now,
            )
            identity.order = order
            identity.save(update_fields=("order",))
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
                order_id=str(order.public_id),
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
            order.refresh_from_db()
            return CheckoutResult(order, payment_transaction, preference.checkout_url)
    except IntegrityError:
        existing_order = user.orders.filter(checkout_idempotency_key=idempotency_key).first()
        if existing_order:
            existing_transaction = existing_order.payment_transactions.order_by(
                "created_at"
            ).first()
            return CheckoutResult(
                existing_order,
                existing_transaction,
                existing_transaction.checkout_url if existing_transaction else "",
            )
        raise
    except InsufficientStock as exc:
        raise CheckoutError("insufficient_stock", "No hay stock suficiente") from exc


def resume_checkout(*, order, cart, user, payment_adapter):
    identity = (
        order.identity_verifications.filter(status="approved").order_by("-created_at").first()
    )
    if not identity:
        raise CheckoutError("identity_pending_review", "La identidad todavía está en revisión")
    if order.user_id != user.pk or cart.user_id != user.pk:
        raise CheckoutError("cart_owner_mismatch", "No encontramos ese carrito")
    now = timezone.now()
    with transaction.atomic():
        locked_order = type(order).objects.select_for_update().get(pk=order.pk)
        existing = locked_order.payment_transactions.order_by("created_at").first()
        if existing:
            return CheckoutResult(locked_order, existing, existing.checkout_url)
        current_profile = (
            BillingProfile.objects.select_for_update()
            .filter(
                pk=locked_order.fiscal_snapshot.get("profile_id"),
                customer__user=user,
            )
            .first()
        )
        if not current_profile or _fiscal_snapshot(current_profile) != locked_order.fiscal_snapshot:
            raise CheckoutError(
                "checkout_changed", "El perfil fiscal cambió y debe confirmarse nuevamente"
            )
        address = None
        if locked_order.fulfillment_method == locked_order.FulfillmentMethod.SHIPPING:
            address = user.addresses.filter(
                street=locked_order.address_snapshot.get("street", ""),
                number=locked_order.address_snapshot.get("number", ""),
                postal_code=locked_order.address_snapshot.get("postal_code", ""),
            ).first()
        effective_quote = _validate_shipping(
            user=user,
            cart=cart,
            fulfillment_method=locked_order.fulfillment_method,
            address=address,
            shipping_quote=locked_order.shipping_quote,
            now=now,
        )
        totals = calculate_cart_totals(cart, at=now)
        expected_total = totals.total + (effective_quote.total_amount if effective_quote else 0)
        if (
            totals.subtotal != locked_order.subtotal_snapshot
            or totals.discount != locked_order.discount_snapshot
            or expected_total != locked_order.total_snapshot
            or (cart.coupon.code if cart.coupon_id else "") != locked_order.coupon_code_snapshot
        ):
            raise CheckoutError(
                "checkout_changed", "El carrito cambió y debe confirmarse nuevamente"
            )
        transition_order_status(
            order=locked_order,
            field="identity_status",
            value=locked_order.IdentityStatus.VERIFIED,
        )
        expiry = now + timezone.timedelta(minutes=20)
        for line in cart.lines.select_related("variant"):
            reservation = create_reservation(
                variant=line.variant,
                quantity=line.quantity,
                reference=str(locked_order.public_id),
                expires_at=expiry,
            )
            locked_order.reservations.add(reservation)
        payment_transaction = PaymentTransaction.objects.create(
            order=locked_order,
            amount=locked_order.total_snapshot,
            currency="ARS",
            expected_collector_id=getattr(payment_adapter, "collector_id", ""),
            live_mode=bool(getattr(payment_adapter, "live_mode", False)),
        )
        preference = payment_adapter.create_preference(
            external_reference=str(payment_transaction.external_reference),
            order_id=str(locked_order.public_id),
            amount=payment_transaction.amount,
            description=f"Pedido {locked_order.public_id}",
            payer_email=user.email,
            idempotency_key=str(payment_transaction.idempotency_key),
            now=now,
        )
        payment_transaction.preference_id = preference.preference_id
        payment_transaction.checkout_url = preference.checkout_url
        payment_transaction.save(update_fields=("preference_id", "checkout_url", "updated_at"))
        transition_order_status(
            order=locked_order,
            field="payment_status",
            value=locked_order.PaymentStatus.PENDING,
        )
        locked_order.refresh_from_db()
        return CheckoutResult(locked_order, payment_transaction, preference.checkout_url)
