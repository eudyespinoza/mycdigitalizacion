import secrets

import pytest
from django.contrib.auth.hashers import make_password

from support.access import (
    issue_guest_session,
    resolve_guest_session,
    verify_recovery_code,
)
from support.models import SupportCase


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
def test_case_number_and_recovery_code_are_non_sequential_and_private():
    case, raw_code = create_case_with_recovery(subject="Consulta por cuadernos")
    another_case, _ = create_case_with_recovery(subject="Consulta por lapices")

    assert case.case_number.startswith("CON-")
    assert case.case_number != another_case.case_number
    assert raw_code not in case.recovery_code_hash
    assert verify_recovery_code(case, raw_code)
