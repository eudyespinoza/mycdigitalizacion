import pytest
from django.contrib.auth.hashers import make_password

from support.models import SupportCase

pytestmark = pytest.mark.django_db


@pytest.fixture
def support_case():
    return SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Consulta con correo opcional",
        category="productos",
        contact_email="guest@example.test",
        recovery_code_hash=make_password("private-code"),
    )


def test_missing_smtp_does_not_block_notification_queue(settings, support_case):
    from support.tasks import queue_support_notification

    settings.EMAIL_HOST = ""

    assert queue_support_notification(support_case, "created") == "disabled"
