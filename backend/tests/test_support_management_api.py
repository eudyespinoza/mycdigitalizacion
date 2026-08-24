import importlib
import io
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
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
    assert row["unread"] is True
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


def test_detail_marks_customer_message_read_without_changing_pending_or_updated_ordering(
    owner_client, support_case
):
    before = support_case.updated_at
    initial_list = owner_client.get("/api/v1/management/support/cases/?unread=1")
    initial_summary = owner_client.get("/api/v1/management/support/summary/")

    assert [row["public_id"] for row in initial_list.json()["results"]] == [
        str(support_case.public_id)
    ]
    assert initial_summary.json() == {"pending": 1, "unread": 1}

    detail = owner_client.get(f"/api/v1/management/support/cases/{support_case.public_id}/")
    assert detail.status_code == 200
    support_case.refresh_from_db()
    assert support_case.staff_last_read_at is not None
    assert support_case.updated_at == before
    assert owner_client.get("/api/v1/management/support/cases/?pending=1").json()["count"] == 1
    read_list = owner_client.get("/api/v1/management/support/cases/?unread=1")
    assert read_list.json()["count"] == 0
    assert owner_client.get("/api/v1/management/support/cases/?pending=1").json()["results"][0][
        "unread"
    ] is False
    assert owner_client.get("/api/v1/management/support/summary/").json() == {
        "pending": 1,
        "unread": 0,
    }

    later = SupportMessage.objects.create(
        case=support_case,
        author_role=SupportMessage.AuthorRole.GUEST,
        body="Nueva respuesta del cliente",
        idempotency_key="later-customer-reply",
    )
    SupportMessage.objects.filter(pk=later.pk).update(
        created_at=support_case.staff_last_read_at + timedelta(seconds=1)
    )

    unread_list = owner_client.get("/api/v1/management/support/cases/?unread=1")
    assert unread_list.json()["count"] == 1
    assert unread_list.json()["results"][0]["unread"] is True
    assert owner_client.get("/api/v1/management/support/summary/").json() == {
        "pending": 1,
        "unread": 1,
    }


def test_noop_case_patch_does_not_create_a_management_audit_event(owner_client, support_case):
    before = ManagementAuditEvent.objects.count()

    response = owner_client.patch(
        f"/api/v1/management/support/cases/{support_case.public_id}/",
        {"priority": support_case.priority},
        format="json",
    )

    assert response.status_code == 200
    assert ManagementAuditEvent.objects.count() == before


def test_support_role_migration_preserves_preexisting_attention_and_owner_groups():
    migration = importlib.import_module("support.migrations.0003_support_role")
    migration.remove_support_roles(django_apps, None)
    Group.objects.filter(name="Atención").delete()
    attention = Group.objects.create(name="Atención")
    owner, _ = Group.objects.get_or_create(name="Owner")
    owner_permission_ids = set(owner.permissions.values_list("id", flat=True))

    migration.add_support_roles(django_apps, None)
    migration.remove_support_roles(django_apps, None)

    attention.refresh_from_db()
    owner.refresh_from_db()
    assert attention.permissions.filter(codename="view_supportcase").exists()
    assert set(owner.permissions.values_list("id", flat=True)) == owner_permission_ids


def test_support_role_migration_reverses_group_created_by_the_migration():
    migration = importlib.import_module("support.migrations.0003_support_role")
    migration.remove_support_roles(django_apps, None)
    Group.objects.filter(name="Atención").delete()

    migration.add_support_roles(django_apps, None)
    attention = Group.objects.get(name="Atención")
    marker_present = attention.permissions.filter(
        codename="support_attention_role_migration_marker"
    ).exists()

    migration.remove_support_roles(django_apps, None)

    assert marker_present
    assert not Group.objects.filter(name="Atención").exists()
    assert not Permission.objects.filter(
        codename="support_attention_role_migration_marker"
    ).exists()


def test_attention_can_list_minimal_active_support_assignees_and_assign_them(
    attention_client, django_user_model, support_case
):
    group = Group.objects.get(name="Atención")
    candidate = django_user_model.objects.create_user(
        email="ada-support@example.test",
        password="StrongPassword!2026",
        first_name="Ada",
        last_name="Support",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    candidate.groups.add(group)
    inactive = django_user_model.objects.create_user(
        email="inactive-support@example.test",
        password="StrongPassword!2026",
        is_staff=True,
        is_active=False,
    )
    inactive.groups.add(group)
    django_user_model.objects.create_user(
        email="customer@example.test", password="StrongPassword!2026"
    )

    response = attention_client.get("/api/v1/management/support/assignees/")

    assert response.status_code == 200
    results = response.json()["results"]
    selected = next(row for row in results if row["id"] == candidate.pk)
    assert set(selected) == {"id", "name", "email"}
    assert selected == {"id": candidate.pk, "name": "Ada Support", "email": candidate.email}
    assert inactive.pk not in {row["id"] for row in results}
    assert all(row["email"] != "customer@example.test" for row in results)

    assigned = attention_client.patch(
        f"/api/v1/management/support/cases/{support_case.public_id}/",
        {"assigned_to": candidate.pk},
        format="json",
    )
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to"]["id"] == candidate.pk


def test_staff_without_support_permission_cannot_list_assignees(django_user_model):
    staff = django_user_model.objects.create_user(
        email="staff@example.test", password="StrongPassword!2026", is_staff=True
    )
    client = APIClient()
    client.force_login(staff)

    assert client.get("/api/v1/management/support/assignees/").status_code == 403
