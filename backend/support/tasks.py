"""Optional, idempotent email notifications for support conversations."""

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from support.models import SupportCase

NOTIFIABLE_EVENTS = frozenset({"created", "customer_reply", "staff_reply", "resolved"})
_IDEMPOTENCY_TIMEOUT_SECONDS = 30 * 24 * 60 * 60


def _email_is_available():
    return bool(getattr(settings, "SUPPORT_EMAIL_AVAILABLE", False) and settings.EMAIL_HOST)


def queue_support_notification(case, event):
    """Queue a notification only after the surrounding transaction commits."""
    if event not in NOTIFIABLE_EVENTS or not _email_is_available():
        return "disabled"
    from django.db import transaction

    transaction.on_commit(lambda: send_support_notification.delay(case.pk, event))
    return "queued"


@shared_task
def send_support_notification(case_id, event):
    """Send one generic notification without including private conversation content."""
    if event not in NOTIFIABLE_EVENTS or not _email_is_available():
        return "disabled"
    case = SupportCase.objects.filter(pk=case_id).only(
        "pk", "case_number", "contact_email"
    ).first()
    if not case or not case.contact_email:
        return "disabled"
    cache_key = f"support-notification:{case.pk}:{event}"
    if not cache.add(cache_key, True, timeout=_IDEMPOTENCY_TIMEOUT_SECONDS):
        return "already_sent"
    try:
        send_mail(
            subject=f"Actualización de tu consulta {case.case_number}",
            message=(
                "Tu consulta recibió una actualización. Ingresá a la sección Consultas "
                "para ver el estado."
            ),
            from_email=getattr(settings, "SUPPORT_NOTIFICATION_FROM_EMAIL", None),
            recipient_list=[case.contact_email],
            fail_silently=False,
        )
    except Exception:
        cache.delete(cache_key)
        return "failed"
    return "sent"
