import secrets

import pytest
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from support.access import (
    issue_guest_session,
    resolve_guest_session,
    verify_recovery_code,
)
from support.models import SupportCase, generate_case_number


def create_case_with_recovery(*, subject):
    raw_code = secrets.token_urlsafe(18)
    case = SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject=subject,
        category="productos",
        recovery_code_hash=make_password(raw_code),
    )
    return case, raw_code


@pytest.mark.django_db
def test_guest_token_is_stored_as_a_hash_and_resolves_by_its_digest():
    session, raw_token = issue_guest_session()

    assert raw_token not in session.token_hash
    assert raw_token not in session.token_digest
    assert resolve_guest_session(raw_token) == session


@pytest.mark.django_db
def test_revoked_guest_token_does_not_resolve():
    session, raw_token = issue_guest_session()
    session.revoked_at = timezone.now()
    session.save(update_fields=("revoked_at",))

    assert resolve_guest_session(raw_token) is None


@pytest.mark.django_db
def test_wrong_guest_token_does_not_resolve():
    issue_guest_session()

    assert resolve_guest_session("not-the-issued-token") is None


@pytest.mark.django_db
def test_case_number_and_recovery_code_are_non_sequential_and_private():
    case, raw_code = create_case_with_recovery(subject="Consulta por cuadernos")
    another_case, _ = create_case_with_recovery(subject="Consulta por lapices")

    assert case.case_number.startswith("CON-")
    assert case.case_number != another_case.case_number
    assert len(case.case_number.rsplit("-", maxsplit=1)[1]) == 14
    assert raw_code not in case.recovery_code_hash
    assert verify_recovery_code(case, raw_code)


def test_case_number_rejects_an_unexpected_kind():
    with pytest.raises(ValueError, match="Unsupported support case kind"):
        generate_case_number("unexpected")


@pytest.mark.django_db
def test_database_rejects_an_unexpected_case_kind():
    invalid_case = SupportCase(
        case_number="CON-2026-INVALIDKIND",
        kind="unexpected",
        subject="Consulta invalida",
        category="productos",
        recovery_code_hash=make_password("code"),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SupportCase.objects.bulk_create([invalid_case])


@pytest.mark.django_db
def test_clearing_contact_email_clears_normalized_email():
    case, _ = create_case_with_recovery(subject="Consulta con contacto")
    case.contact_email = "cliente@example.test"
    case.save()
    case.contact_email = ""
    case.save()
    case.refresh_from_db()

    assert case.contact_email_normalized == ""
