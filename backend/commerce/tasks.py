import logging

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from accounts.models import EmailVerificationChallenge
from commerce.models import (
    NotificationAttempt,
    PaymentTransaction,
    PaymentWebhookEvent,
    Shipment,
    StockReservation,
)
from commerce.payments import PaymentMismatch, apply_payment, process_webhook_event
from commerce.provider_config import get_carrier_adapter, get_payment_adapter
from commerce.services import release_reservation
from providers import ProviderError

logger = logging.getLogger(__name__)


@shared_task
def release_expired_reservations():
    ids = list(
        StockReservation.objects.filter(
            status=StockReservation.Status.ACTIVE, expires_at__lte=timezone.now()
        ).values_list("pk", flat=True)
    )
    for reservation in StockReservation.objects.filter(pk__in=ids):
        release_reservation(reservation)
    return len(ids)


@shared_task
def process_payment_webhook(event_id):
    event = PaymentWebhookEvent.objects.get(pk=event_id)
    try:
        process_webhook_event(event=event, adapter=get_payment_adapter())
    except (ProviderError, PaymentMismatch) as exc:
        if isinstance(exc, ProviderError):
            PaymentWebhookEvent.objects.filter(pk=event_id).update(
                status="queued", staff_diagnostics=exc.code
            )
        logger.warning(
            "payment_webhook_processing_failed",
            extra={"event_id": event_id, "failure_code": getattr(exc, "code", "mismatch")},
        )
        raise


@shared_task
def reconcile_pending_payments():
    adapter = get_payment_adapter()
    reconciled = 0
    for payment_transaction in PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.PENDING
    ).exclude(payment_id__isnull=True):
        try:
            payment = adapter.fetch_payment(payment_transaction.payment_id)
            apply_payment(transaction=payment_transaction, payment=payment)
            reconciled += 1
        except ProviderError as exc:
            logger.warning(
                "payment_reconciliation_failed",
                extra={"transaction_id": payment_transaction.pk, "failure_code": exc.code},
            )
    return reconciled


@shared_task
def reconcile_tracking():
    adapter = get_carrier_adapter()
    reconciled = 0
    for shipment in Shipment.objects.exclude(status__in=("delivered", "returned")):
        if not shipment.tracking_number:
            continue
        try:
            result = adapter.tracking(shipment.tracking_number)
        except ProviderError as exc:
            logger.warning(
                "tracking_reconciliation_failed",
                extra={"shipment_id": shipment.pk, "failure_code": exc.code},
            )
            continue
        shipment.status = str(result.get("status") or shipment.status)
        shipment.provider_summary = {"last_event": str(result.get("last_event") or "")}
        shipment.save(update_fields=("status", "provider_summary", "updated_at"))
        reconciled += 1
    return reconciled


@shared_task
def retry_safe_notifications():
    # Delivery is intentionally not fabricated when no notification provider exists.
    # Attempts remain retryable and the operational reason is stored without PII.
    now = timezone.now()
    attempts = NotificationAttempt.objects.filter(status="pending", next_attempt_at__lte=now)
    count = attempts.update(
        attempts=F("attempts") + 1,
        next_attempt_at=now + timezone.timedelta(minutes=15),
        last_error="notification_provider_not_configured",
    )
    return count


@shared_task
def expire_verification_challenges():
    now = timezone.now()
    return EmailVerificationChallenge.objects.filter(
        consumed_at__isnull=True, locked_at__isnull=True, expires_at__lt=now
    ).update(locked_at=now)
