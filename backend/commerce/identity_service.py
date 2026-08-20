from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from commerce.models import IdentityVerification
from providers import ProviderNotConfigured, ProviderRejected, ProviderUnavailable


class IdentityRejected(ValueError):
    code = "identity_rejected"


def _masked_document(customer):
    value = customer.get_dni()
    return f"••••{value[-4:]}"


def validate_identity(*, customer, adapter, consent):
    now = timezone.now()
    base = {
        "user": customer.user,
        "consent_version": customer.consent_version,
        "consented_at": now,
        "attempt_number": customer.user.identity_verifications.count() + 1,
        "masked_audit": {"document": _masked_document(customer)},
    }
    try:
        result = adapter.verify(dni=customer.get_dni(), consent=consent)
    except (ProviderNotConfigured, ProviderUnavailable) as exc:
        return IdentityVerification.objects.create(
            **base,
            status=IdentityVerification.Status.PENDING_REVIEW,
            staff_diagnostics=exc.diagnostics or exc.code,
        )
    except ProviderRejected as exc:
        IdentityVerification.objects.create(
            **base,
            status=IdentityVerification.Status.REJECTED,
            staff_diagnostics=exc.diagnostics or exc.code,
        )
        raise IdentityRejected("No pudimos validar tu identidad") from exc
    approved = {**base, "masked_audit": {**base["masked_audit"], **result.masked_data}}
    return IdentityVerification.objects.create(
        **approved,
        status=IdentityVerification.Status.APPROVED,
        provider_reference=result.reference,
    )


@transaction.atomic
def approve_identity_manually(*, attempt, actor, reason):
    if not actor.is_staff:
        raise PermissionDenied("Staff access is required")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("Manual approval requires a reason")
    locked = IdentityVerification.objects.select_for_update().get(pk=attempt.pk)
    locked.status = IdentityVerification.Status.APPROVED
    locked.reviewed_by = actor
    locked.review_reason = normalized_reason
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=("status", "reviewed_by", "review_reason", "reviewed_at"))
    return locked
