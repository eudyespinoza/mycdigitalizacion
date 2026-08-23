"""Transactional case and message operations for the support domain."""

import secrets
from dataclasses import dataclass

from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction

from support.access import verify_recovery_code
from support.attachments import validate_support_files
from support.models import SupportCase, SupportGuestAccess, SupportMessage
from support.storage import delete_persisted_uploads, persist_validated_uploads


@dataclass(frozen=True)
class CaseCreationResult:
    case: SupportCase
    message: SupportMessage
    recovery_code: str | None


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", actor is not None) else None


def _creation_retry(actor, guest_session, idempotency_key):
    messages = SupportMessage.objects.filter(idempotency_key=idempotency_key).select_related("case")
    if actor:
        return messages.filter(case__customer=actor).first()
    if guest_session:
        return messages.filter(case__guest_accesses__session=guest_session).first()
    return None


def _lock_creation_owner(actor, guest_session):
    if actor:
        return actor.__class__.objects.select_for_update().get(pk=actor.pk), guest_session
    if guest_session:
        return None, guest_session.__class__.objects.select_for_update().get(pk=guest_session.pk)
    raise ValueError("Case creation requires an authenticated actor or guest session")


def create_case(actor, guest_session, payload, files, idempotency_key):
    actor = _actor_or_none(actor)
    persisted_attachments = []
    try:
        with transaction.atomic():
            actor, guest_session = _lock_creation_owner(actor, guest_session)
            existing = _creation_retry(actor, guest_session, idempotency_key)
            if existing:
                return CaseCreationResult(case=existing.case, message=existing, recovery_code=None)

            validated = validate_support_files(files)
            raw_recovery_code = secrets.token_urlsafe(18)
            case = SupportCase.objects.create(
                kind=payload["kind"],
                subject=payload["subject"].strip(),
                category=payload["category"],
                customer=actor,
                contact_name=str(payload.get("contact_name", "")).strip(),
                contact_email=str(payload.get("contact_email", "")).strip(),
                contact_phone=str(payload.get("contact_phone", "")).strip(),
                order=payload.get("order"),
                product=payload.get("product"),
                source_url=str(payload.get("source_url", "")).strip(),
                recovery_code_hash=make_password(raw_recovery_code),
            )
            if guest_session:
                SupportGuestAccess.objects.create(case=case, session=guest_session)
            message = SupportMessage.objects.create(
                case=case,
                author=actor,
                author_role=(
                    SupportMessage.AuthorRole.CUSTOMER if actor else SupportMessage.AuthorRole.GUEST
                ),
                body=payload["body"].strip(),
                idempotency_key=idempotency_key,
            )
            persisted_attachments = persist_validated_uploads(message, validated)
            transition_after_message(case, message.author_role)
        return CaseCreationResult(case=case, message=message, recovery_code=raw_recovery_code)
    except Exception:
        delete_persisted_uploads(persisted_attachments)
        raise


def _next_status(role):
    if role == SupportMessage.AuthorRole.STAFF:
        return SupportCase.Status.WAITING_CUSTOMER
    if role in {SupportMessage.AuthorRole.CUSTOMER, SupportMessage.AuthorRole.GUEST}:
        return SupportCase.Status.WAITING_STAFF
    raise ValueError("Invalid support message role")


def transition_after_message(case, role):
    case.status = _next_status(role)
    case.save(update_fields=("status", "updated_at"))


def append_message(case, actor, role, body, files, idempotency_key):
    persisted_attachments = []
    try:
        with transaction.atomic():
            locked_case = SupportCase.objects.select_for_update().get(pk=case.pk)
            existing = SupportMessage.objects.filter(
                case=locked_case, idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing
            if locked_case.status == SupportCase.Status.CLOSED:
                raise PermissionDenied("El caso está cerrado")
            _next_status(role)
            validated = validate_support_files(files)
            actor = _actor_or_none(actor)
            try:
                with transaction.atomic():
                    message = SupportMessage.objects.create(
                        case=locked_case,
                        author=actor,
                        author_role=role,
                        body=body.strip(),
                        idempotency_key=idempotency_key,
                    )
            except IntegrityError:
                return SupportMessage.objects.get(case=locked_case, idempotency_key=idempotency_key)
            persisted_attachments = persist_validated_uploads(message, validated)
            transition_after_message(locked_case, role)
        case.status = locked_case.status
        case.updated_at = locked_case.updated_at
        return message
    except Exception:
        delete_persisted_uploads(persisted_attachments)
        raise


@transaction.atomic
def claim_case(case, user, recovery_code):
    locked_case = SupportCase.objects.select_for_update().get(pk=case.pk)
    if not verify_recovery_code(locked_case, recovery_code):
        raise PermissionDenied("El código de recuperación no es válido")
    locked_case.customer = user
    locked_case.save(update_fields=("customer", "updated_at"))
    SupportGuestAccess.objects.filter(case=locked_case).delete()
    case.customer_id = user.pk
    return locked_case
