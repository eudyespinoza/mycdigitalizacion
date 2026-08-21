from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import ProductVariant
from commerce.models import (
    InventoryMovement,
    PaymentTransaction,
    PaymentWebhookEvent,
    Refund,
    StockReservation,
)
from commerce.services import consume_reservation, release_reservation, transition_order_status


def parse_signature(value):
    parsed = {}
    for part in (value or "").split(","):
        key, separator, raw = part.partition("=")
        if separator:
            parsed[key.strip()] = raw.strip()
    return parsed.get("ts"), parsed.get("v1")


def validate_webhook_signature(
    *, data_id, request_id, signature_header, secret, now, tolerance_seconds=300
):
    timestamp, signature = parse_signature(signature_header)
    if not all((data_id, request_id, timestamp, signature, secret)):
        return False
    try:
        raw_timestamp = int(timestamp)
    except ValueError:
        return False
    timestamp_seconds = raw_timestamp / 1000 if raw_timestamp > 9_999_999_999 else raw_timestamp
    if abs(now.timestamp() - timestamp_seconds) > tolerance_seconds:
        return False
    manifest = f"id:{str(data_id).lower()};request-id:{request_id};ts:{timestamp};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookRejected(ValueError):
    code = "invalid_webhook_signature"


class PaymentMismatch(ValueError):
    code = "payment_mismatch"


@dataclass(frozen=True)
class WebhookIngestResult:
    event: PaymentWebhookEvent
    duplicate: bool


def _event_payload(raw_body):
    try:
        value = json.loads(raw_body.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _nested(payload, *keys):
    value = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def ingest_webhook(
    *,
    raw_body,
    data_id,
    headers,
    secret,
    enqueue,
    now=None,
    tolerance_seconds=300,
):
    checked_at = now or timezone.now()
    payload = _event_payload(raw_body)
    raw_hash = hashlib.sha256(raw_body).hexdigest()
    payment_id = str(data_id or "")
    event_id = str(payload.get("id") or f"body-{raw_hash}")
    request_id = str(headers.get("x-request-id") or headers.get("X-Request-Id") or "")
    valid = validate_webhook_signature(
        data_id=payment_id,
        request_id=request_id,
        signature_header=headers.get("x-signature") or headers.get("X-Signature"),
        secret=secret,
        now=checked_at,
        tolerance_seconds=tolerance_seconds,
    )
    created = False
    try:
        with transaction.atomic():
            event = PaymentWebhookEvent.objects.create(
                event_id=event_id,
                request_id=request_id,
                payment_id=payment_id,
                raw_body_hash=raw_hash,
            )
            created = True
    except IntegrityError:
        event = PaymentWebhookEvent.objects.get(provider="mercadopago", event_id=event_id)
        if event.signature_valid:
            return WebhookIngestResult(event, True)
        if not valid:
            return WebhookIngestResult(event, True)
    if not valid:
        if created:
            event.signature_valid = False
            event.status = "rejected"
            event.staff_diagnostics = "signature_or_timestamp_invalid"
            event.save(
                update_fields=("signature_valid", "status", "staff_diagnostics", "updated_at")
            )
        raise WebhookRejected("Firma de webhook inválida")
    event.request_id = request_id
    event.payment_id = payment_id
    event.raw_body_hash = raw_hash
    event.signature_valid = True
    event.status = "queued"
    event.staff_diagnostics = ""
    event.processed_at = None
    event.save(
        update_fields=(
            "request_id",
            "payment_id",
            "raw_body_hash",
            "signature_valid",
            "status",
            "staff_diagnostics",
            "processed_at",
            "updated_at",
        )
    )
    transaction.on_commit(lambda: enqueue(event.pk))
    return WebhookIngestResult(event, False)


def _payment_amount(payment):
    value = payment.get("transaction_amount")
    if value is None:
        value = _nested(payment, "transaction_details", "total_paid_amount")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None


def _mismatch_reason(transaction, payment):
    if str(payment.get("external_reference") or "") != str(transaction.external_reference):
        return "external_reference_mismatch"
    if _payment_amount(payment) != transaction.amount:
        return "amount_mismatch"
    if str(payment.get("currency_id") or "").upper() != transaction.currency:
        return "currency_mismatch"
    collector = payment.get("collector_id") or _nested(payment, "collector", "id")
    if (
        transaction.expected_collector_id
        and str(collector or "") != transaction.expected_collector_id
    ):
        return "collector_mismatch"
    if payment.get("live_mode") is None or bool(payment["live_mode"]) != transaction.live_mode:
        return "live_mode_mismatch"
    provider_order_id = _nested(payment, "metadata", "order_id")
    if str(provider_order_id or "") != str(transaction.order.public_id):
        return "order_mismatch"
    return ""


def _safe_payment_summary(payment):
    return {
        key: payment.get(key)
        for key in (
            "id",
            "status",
            "status_detail",
            "external_reference",
            "currency_id",
            "live_mode",
        )
        if payment.get(key) is not None
    }


@transaction.atomic
def _apply_payment_atomic(*, payment_transaction, payment):
    payment_transaction = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment_transaction.pk)
    )
    order = (
        type(payment_transaction.order)
        .objects.select_for_update()
        .get(pk=payment_transaction.order_id)
    )
    payment_transaction.order = order
    mismatch = _mismatch_reason(payment_transaction, payment)
    if mismatch:
        payment_transaction.status = PaymentTransaction.Status.NEEDS_ATTENTION
        payment_transaction.staff_diagnostics = mismatch
        payment_transaction.provider_summary = _safe_payment_summary(payment)
        payment_transaction.save(
            update_fields=("status", "staff_diagnostics", "provider_summary", "updated_at")
        )
        transition_order_status(
            order=order, field="payment_status", value=order.PaymentStatus.NEEDS_ATTENTION
        )
        return payment_transaction, True

    provider_status = str(payment.get("status") or "").lower()
    if order.payment_status == order.PaymentStatus.PAID and provider_status in {
        "pending",
        "in_process",
        "authorized",
    }:
        return payment_transaction, False
    payment_transaction.payment_id = (
        str(payment.get("id") or payment_transaction.payment_id or "") or None
    )
    payment_transaction.provider_status = provider_status
    payment_transaction.provider_summary = _safe_payment_summary(payment)
    if provider_status in {"approved", "paid"}:
        consumed = [consume_reservation(item) for item in order.reservations.all()]
        if any(item.status != StockReservation.Status.CONSUMED for item in consumed):
            payment_transaction.status = PaymentTransaction.Status.NEEDS_ATTENTION
            payment_transaction.staff_diagnostics = "reservation_expired_before_payment"
            payment_transaction.save()
            transition_order_status(
                order=order, field="payment_status", value=order.PaymentStatus.NEEDS_ATTENTION
            )
            return payment_transaction, True
        payment_transaction.status = PaymentTransaction.Status.APPROVED
        payment_transaction.approved_at = timezone.now()
        payment_transaction.staff_diagnostics = ""
        payment_transaction.save()
        transition_order_status(order=order, field="payment_status", value=order.PaymentStatus.PAID)
    elif provider_status in {"rejected", "cancelled", "expired"}:
        payment_transaction.status = PaymentTransaction.Status.REJECTED
        payment_transaction.save()
        transition_order_status(
            order=order, field="payment_status", value=order.PaymentStatus.FAILED
        )
    elif provider_status in {"refunded", "charged_back", "charged_back_pending"}:
        payment_transaction.status = PaymentTransaction.Status.NEEDS_ATTENTION
        payment_transaction.staff_diagnostics = f"provider_terminal_{provider_status}"
        payment_transaction.save()
        transition_order_status(
            order=order, field="payment_status", value=order.PaymentStatus.NEEDS_ATTENTION
        )
        return payment_transaction, True
    return payment_transaction, False


def apply_payment(*, transaction, payment):
    payment_transaction, needs_attention = _apply_payment_atomic(
        payment_transaction=transaction, payment=payment
    )
    if needs_attention:
        raise PaymentMismatch("El pago requiere revisión")
    return payment_transaction


def process_webhook_event(*, event, adapter):
    with transaction.atomic():
        event = PaymentWebhookEvent.objects.select_for_update().get(pk=event.pk)
        if event.processed_at or event.status == "processing":
            return event
        event.status = "processing"
        event.updated_at = timezone.now()
        event.save(update_fields=("status", "updated_at"))
    payment = adapter.fetch_payment(event.payment_id)
    transaction_record = PaymentTransaction.objects.filter(payment_id=event.payment_id).first()
    if transaction_record is None:
        transaction_record = PaymentTransaction.objects.get(
            external_reference=payment.get("external_reference")
        )
    try:
        apply_payment(transaction=transaction_record, payment=payment)
    except PaymentMismatch:
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(
            status="needs_attention",
            staff_diagnostics="payment_validation_failed",
            processed_at=timezone.now(),
        )
        raise
    PaymentWebhookEvent.objects.filter(pk=event.pk).update(
        status="processed", processed_at=timezone.now()
    )
    event.refresh_from_db()
    return event


class RefundError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def refund_order(*, order, adapter, idempotency_key):
    with transaction.atomic():
        order = type(order).objects.select_for_update().get(pk=order.pk)
        existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
        if existing and existing.order_id != order.pk:
            raise RefundError("refund_idempotency_conflict", "La clave de reembolso ya fue usada")
        if existing and existing.status == "approved":
            return existing
        payment_transaction = (
            PaymentTransaction.objects.select_for_update().get(pk=existing.transaction_id)
            if existing
            else order.payment_transactions.select_for_update()
            .filter(status=PaymentTransaction.Status.APPROVED)
            .order_by("-created_at")
            .first()
        )
        if not payment_transaction or not payment_transaction.payment_id:
            raise RefundError(
                "refund_not_allowed", "El pedido no tiene un pago aprobado reembolsable"
            )
        if existing:
            refund = existing
        else:
            try:
                with transaction.atomic():
                    refund = Refund.objects.create(
                        order=order,
                        transaction=payment_transaction,
                        idempotency_key=idempotency_key,
                        amount=payment_transaction.amount,
                    )
            except IntegrityError:
                winner = Refund.objects.select_for_update().get(
                    idempotency_key=idempotency_key
                )
                if winner.order_id != order.pk:
                    raise RefundError(
                        "refund_idempotency_conflict",
                        "La clave de reembolso ya fue usada",
                    ) from None
                refund = winner
                payment_transaction = PaymentTransaction.objects.select_for_update().get(
                    pk=winner.transaction_id
                )
                if refund.status == "approved":
                    return refund
        response = adapter.refund(
            payment_transaction.payment_id,
            amount=None,
            idempotency_key=str(idempotency_key),
        )
        refund.provider_refund_id = str(response.get("id") or "")
        refund.status = str(response.get("status") or "pending")
        if refund.status != "approved":
            refund.save(update_fields=("provider_refund_id", "status", "updated_at"))
            return refund
        if order.fulfillment_status in {
            order.FulfillmentStatus.SHIPPED,
            order.FulfillmentStatus.FULFILLED,
        }:
            refund.return_required = True
        else:
            for reservation in order.reservations.select_related("variant"):
                if reservation.status == StockReservation.Status.ACTIVE:
                    release_reservation(reservation)
                elif (
                    reservation.status == StockReservation.Status.CONSUMED
                    and reservation.tracks_inventory
                ):
                    variant = ProductVariant.objects.select_for_update().get(
                        pk=reservation.variant_id
                    )
                    variant.on_hand += reservation.quantity
                    variant.save(update_fields=("on_hand",))
                    InventoryMovement.objects.create(
                        variant=variant,
                        reservation=reservation,
                        kind=InventoryMovement.Kind.REFUND,
                        quantity_delta=reservation.quantity,
                        reference=str(refund.idempotency_key),
                    )
                    refund.stock_restored = True
        refund.save(
            update_fields=(
                "provider_refund_id",
                "status",
                "stock_restored",
                "return_required",
                "updated_at",
            )
        )
        payment_transaction.status = PaymentTransaction.Status.REFUNDED
        payment_transaction.save(update_fields=("status", "updated_at"))
        transition_order_status(
            order=order, field="payment_status", value=order.PaymentStatus.REFUNDED
        )
        return refund
