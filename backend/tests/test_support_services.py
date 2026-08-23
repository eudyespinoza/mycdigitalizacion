import io
import secrets

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from support.access import issue_guest_session
from support.models import SupportAttachment, SupportCase, SupportGuestAccess
from support.services import append_message, claim_case, create_case


def png_upload(name="captura.png"):
    image = Image.new("RGB", (24, 16), "red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user("staff@example.test", password="password")


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user("customer@example.test", password="password")


@pytest.fixture
def case(customer):
    return SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Consulta",
        category="productos",
        customer=customer,
        recovery_code_hash=make_password("private-code"),
    )


@pytest.mark.django_db
def test_staff_and_customer_messages_drive_waiting_state(case, staff, customer):
    append_message(
        case=case,
        actor=staff,
        role="staff",
        body="¿Podés enviar una foto?",
        files=[],
        idempotency_key="staff-1",
    )
    case.refresh_from_db()
    assert case.status == SupportCase.Status.WAITING_CUSTOMER

    append_message(
        case=case,
        actor=customer,
        role="customer",
        body="Adjunto la foto",
        files=[],
        idempotency_key="customer-1",
    )
    case.refresh_from_db()
    assert case.status == SupportCase.Status.WAITING_STAFF


@pytest.mark.django_db
def test_message_idempotency_returns_existing_message_without_repeating_transition(case, customer):
    first = append_message(
        case=case,
        actor=customer,
        role="customer",
        body="Hola",
        files=[],
        idempotency_key="same-key",
    )
    case.refresh_from_db()
    first_updated_at = case.updated_at

    second = append_message(
        case=case,
        actor=customer,
        role="customer",
        body="Mensaje distinto",
        files=[],
        idempotency_key="same-key",
    )
    case.refresh_from_db()

    assert first.pk == second.pk
    assert case.messages.count() == 1
    assert case.updated_at == first_updated_at


@pytest.mark.django_db
def test_message_idempotency_does_not_persist_duplicate_files(case, customer, settings, tmp_path):
    settings.SUPPORT_PRIVATE_MEDIA_ROOT = tmp_path

    first = append_message(
        case=case,
        actor=customer,
        role="customer",
        body="Hola",
        files=[png_upload()],
        idempotency_key="same-key",
    )
    second = append_message(
        case=case,
        actor=customer,
        role="customer",
        body="Hola",
        files=[png_upload("otra.png")],
        idempotency_key="same-key",
    )

    assert first.pk == second.pk
    assert SupportAttachment.objects.filter(message=first).count() == 1
    assert len([path for path in tmp_path.rglob("*") if path.is_file()]) == 2


@pytest.mark.django_db
def test_create_case_returns_recovery_code_once_and_grants_guest_access():
    session, _ = issue_guest_session()
    result = create_case(
        actor=None,
        guest_session=session,
        payload={
            "kind": "consultation",
            "subject": "Consulta por cuadernos",
            "category": "productos",
            "contact_name": "Invitada",
            "contact_email": "invitada@example.test",
            "body": "Necesito ayuda",
        },
        files=[],
        idempotency_key="create-1",
    )

    assert result.recovery_code
    assert result.recovery_code not in result.case.recovery_code_hash
    assert SupportGuestAccess.objects.filter(case=result.case, session=session).exists()
    assert result.message.case_id == result.case.pk

    retry = create_case(
        actor=None,
        guest_session=session,
        payload={
            "kind": "consultation",
            "subject": "Distinto",
            "category": "productos",
            "body": "Distinto",
        },
        files=[],
        idempotency_key="create-1",
    )
    assert retry.case.pk == result.case.pk
    assert retry.recovery_code is None


@pytest.mark.django_db
def test_claim_case_requires_private_recovery_code_even_when_email_matches(case, customer):
    case.contact_email = customer.email
    case.save(update_fields=("contact_email", "contact_email_normalized"))

    with pytest.raises(PermissionDenied):
        claim_case(case=case, user=customer, recovery_code="wrong-code")

    claimed = claim_case(case=case, user=customer, recovery_code="private-code")
    case.refresh_from_db()
    assert claimed.pk == case.pk
    assert case.customer_id == customer.pk


@pytest.mark.django_db
def test_closed_case_rejects_new_messages(case, customer):
    case.status = SupportCase.Status.CLOSED
    case.save(update_fields=("status",))

    with pytest.raises(PermissionDenied):
        append_message(
            case=case,
            actor=customer,
            role="customer",
            body="Hola",
            files=[],
            idempotency_key=secrets.token_hex(),
        )


@pytest.mark.django_db
def test_invalid_message_role_does_not_leave_private_files(case, customer, settings, tmp_path):
    settings.SUPPORT_PRIVATE_MEDIA_ROOT = tmp_path

    with pytest.raises(ValueError):
        append_message(
            case=case,
            actor=customer,
            role="invalid",
            body="Hola",
            files=[png_upload()],
            idempotency_key="invalid-role",
        )

    assert not case.messages.exists()
    assert not list(tmp_path.rglob("*"))
