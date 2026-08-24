import io

import pytest
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from backoffice.models import ManagementAuditEvent
from support.models import SupportAttachment, SupportCase, SupportMessage

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(owner)
    return client


@pytest.fixture
def attention_client(django_user_model):
    attention = django_user_model.objects.create_user(
        email="attention@example.test",
        password="StrongPassword!2026",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    attention.groups.add(Group.objects.get(name="Atención"))
    client = APIClient()
    client.force_login(attention)
    return client


@pytest.fixture
def support_case():
    case = SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Consulta por cuadernos",
        category="productos",
        contact_name="Ada Lovelace",
        contact_email="ada@example.test",
        recovery_code_hash=make_password("private-code"),
    )
    SupportMessage.objects.create(
        case=case,
        author_role=SupportMessage.AuthorRole.GUEST,
        body="Contenido privado del cliente",
        idempotency_key="initial-message",
    )
    case.status = SupportCase.Status.WAITING_STAFF
    case.save(update_fields=("status", "updated_at"))
    return case


def test_attention_role_can_filter_reply_assign_and_list_without_message_bodies(
    attention_client, django_user_model, support_case
):
    assignee = django_user_model.objects.create_user(
        email="assignee@example.test", password="StrongPassword!2026", is_staff=True
    )

    listed = attention_client.get("/api/v1/management/support/cases/?pending=1")

    assert listed.status_code == 200
    row = listed.json()["results"][0]
    assert row["case_number"] == support_case.case_number
    assert "messages" not in row
    assert "body" not in row

    patched = attention_client.patch(
        f"/api/v1/management/support/cases/{support_case.public_id}/",
        {"assigned_to": assignee.pk, "priority": "high"},
        format="json",
    )
    assert patched.status_code == 200
    assert patched.json()["assigned_to"]["id"] == assignee.pk

    replied = attention_client.post(
        f"/api/v1/management/support/cases/{support_case.public_id}/messages/",
        {"body": "Te ayudamos", "idempotency_key": "reply-1"},
        format="multipart",
    )
    assert replied.status_code == 201
    support_case.refresh_from_db()
    assert support_case.status == SupportCase.Status.WAITING_CUSTOMER


def test_management_detail_attachment_and_summary_are_authorized_and_audit_is_safe(
    owner_client, settings, support_case, tmp_path
):
    settings.SUPPORT_PRIVATE_MEDIA_ROOT = tmp_path
    image = Image.new("RGB", (12, 12), "red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    attachment = SimpleUploadedFile("proof.png", output.getvalue(), content_type="image/png")

    replied = owner_client.post(
        f"/api/v1/management/support/cases/{support_case.public_id}/messages/",
        {
            "body": "Contenido privado del equipo",
            "idempotency_key": "reply-with-file",
            "attachments": [attachment],
        },
        format="multipart",
    )
    assert replied.status_code == 201
    stored = SupportAttachment.objects.get()

    detail = owner_client.get(f"/api/v1/management/support/cases/{support_case.public_id}/")
    assert detail.status_code == 200
    assert [message["body"] for message in detail.json()["messages"]] == [
        "Contenido privado del cliente",
        "Contenido privado del equipo",
    ]
    download = owner_client.get(f"/api/v1/management/support/attachments/{stored.public_id}/")
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith("attachment;")
    summary = owner_client.get("/api/v1/management/support/summary/")
    assert summary.status_code == 200
    assert set(summary.json()) == {"pending", "unread"}
    event = ManagementAuditEvent.objects.latest("created_at")
    assert "Contenido privado del equipo" not in str(event.metadata)
    assert str(tmp_path) not in str(event.metadata)


def test_staff_without_support_permissions_is_forbidden(django_user_model, support_case):
    unrelated = django_user_model.objects.create_user(
        email="unrelated@example.test", password="StrongPassword!2026", is_staff=True
    )
    client = APIClient()
    client.force_login(unrelated)

    assert client.get("/api/v1/management/support/cases/").status_code == 403


def test_staff_with_read_only_support_permission_cannot_mutate(django_user_model, support_case):
    reader = django_user_model.objects.create_user(
        email="reader@example.test", password="StrongPassword!2026", is_staff=True
    )
    reader.user_permissions.add(Permission.objects.get(codename="view_supportcase"))
    client = APIClient()
    client.force_login(reader)

    assert client.get("/api/v1/management/support/cases/").status_code == 200
    assert (
        client.patch(
            f"/api/v1/management/support/cases/{support_case.public_id}/",
            {"priority": "high"},
            format="json",
        ).status_code
        == 403
    )
