import logging

from celery import shared_task
from django.db.models import F, Q
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
from commerce.services import release_expired_coupon_redemptions, release_reservation
from commerce.shipping import ShipmentError, create_order_shipment
from providers import ProviderError

logger = logging.getLogger(__name__)


@shared_task
def release_expired_reservations():
    release_expired_coupon_redemptions()
    ids = list(
        StockReservation.objects.filter(
            status=StockReservation.Status.ACTIVE, expires_at__lte=timezone.now()
        ).values_list("pk", flat=True)
    )
    for reservation in StockReservation.objects.filter(pk__in=ids):
        release_reservation(reservation)
    return len(ids)


@shared_task(
    autoretry_for=(ProviderError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
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
    except Exception:
        PaymentWebhookEvent.objects.filter(pk=event_id).update(
            status="queued", staff_diagnostics="unexpected_processing_failure"
        )
        raise


@shared_task
def sweep_stale_webhook_events(*, enqueue=None, now=None):
    checked_at = now or timezone.now()
    cutoff = checked_at - timezone.timedelta(minutes=5)
    event_ids = list(
        PaymentWebhookEvent.objects.filter(updated_at__lte=cutoff)
        .filter(Q(status="processing") | Q(status="queued"))
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    PaymentWebhookEvent.objects.filter(pk__in=event_ids).update(
        status="queued",
        staff_diagnostics="stale_processing_recovered",
        updated_at=checked_at,
    )
    enqueue_event = enqueue or process_payment_webhook.delay
    for event_id in event_ids:
        enqueue_event(event_id)
    return len(event_ids)


@shared_task
def reconcile_pending_payments():
    adapter = get_payment_adapter()
    reconciled = 0
    for payment_transaction in PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.PENDING
    ):
        try:
            payment = (
                adapter.fetch_payment(payment_transaction.payment_id)
                if payment_transaction.payment_id
                else adapter.find_payment(
                    external_reference=str(payment_transaction.external_reference),
                    preference_id=payment_transaction.preference_id,
                )
            )
            if not payment:
                continue
            apply_payment(transaction=payment_transaction, payment=payment)
            reconciled += 1
        except (ProviderError, PaymentMismatch) as exc:
            logger.warning(
                "payment_reconciliation_failed",
                extra={
                    "transaction_id": payment_transaction.pk,
                    "failure_code": getattr(exc, "code", "payment_mismatch"),
                },
            )
    return reconciled


@shared_task
def reconcile_tracking():
    reconciled = 0
    for shipment in Shipment.objects.exclude(status__in=("delivered", "returned")):
        if not shipment.tracking_number:
            continue
        try:
            adapter = get_carrier_adapter(shipment.provider)
            result = adapter.tracking(shipment.tracking_number)
        except ProviderError as exc:
            logger.warning(
                "tracking_reconciliation_failed",
                extra={"shipment_id": shipment.pk, "failure_code": exc.code},
            )
            continue
        tracking = result[0] if isinstance(result, list) and result else result
        events = tracking.get("events", []) if isinstance(tracking, dict) else []
        last_event = events[0] if events else {}
        shipment.status = str(
            last_event.get("event")
            or (tracking.get("estado") if isinstance(tracking, dict) else "")
            or shipment.status
        ).lower()
        shipment.provider_summary = {"last_event": str(last_event.get("event") or "")}
        shipment.save(update_fields=("status", "provider_summary", "updated_at"))
        reconciled += 1
    return reconciled


@shared_task
def resume_pending_shipments():
    recovered = 0
    shipment_ids = list(
        Shipment.objects.filter(status="importing").order_by("pk").values_list("pk", flat=True)
    )
    for shipment in Shipment.objects.select_related("order").filter(pk__in=shipment_ids):
        try:
            adapter = get_carrier_adapter(shipment.provider)
            completed = create_order_shipment(order=shipment.order, adapter=adapter)
        except (ProviderError, ShipmentError) as exc:
            logger.warning(
                "shipment_import_recovery_failed",
                extra={
                    "shipment_id": shipment.pk,
                    "failure_code": getattr(exc, "code", "shipment_error"),
                },
            )
            continue
        if completed.status == "imported":
            recovered += 1
    return recovered


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
