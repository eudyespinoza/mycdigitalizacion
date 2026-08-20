import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from backoffice.models import ManagementAuditEvent
from config.admin_roles import sync_admin_roles

pytestmark = pytest.mark.django_db


def owner_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="store-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(owner)
    return client, owner


def test_management_users_can_be_created_with_least_privilege_role(django_user_model):
    sync_admin_roles()
    client, owner = owner_client(django_user_model)

    created = client.post(
        "/api/v1/management/users/",
        {
            "email": "catalogo@example.test",
            "first_name": "Carla",
            "last_name": "Catálogo",
            "password": "StrongPassword!2026",
            "role_names": ["Catalog"],
            "is_active": True,
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["role_names"] == ["Catalog"]
    staff = django_user_model.objects.get(email="catalogo@example.test")
    assert staff.is_staff is True
    assert staff.groups.get().name == "Catalog"
    assert owner.management_audit_events.filter(action="staff.created").exists()


def test_owner_cannot_deactivate_own_account(django_user_model):
    client, owner = owner_client(django_user_model)
    response = client.patch(
        f"/api/v1/management/users/{owner.pk}/",
        {"is_active": False},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "owner_self_lockout"


def test_management_audit_is_read_only_and_searchable(django_user_model):
    client, owner = owner_client(django_user_model)
    ManagementAuditEvent.objects.create(
        actor=owner,
        action="settings.updated",
        resource="site_settings",
        object_reference="1",
        metadata={"changed_fields": ["announcement"]},
    )

    response = client.get("/api/v1/management/audit/?search=settings")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["actor"] == owner.email
    assert client.post("/api/v1/management/audit/", {}, format="json").status_code == 405


def test_django_admin_route_and_application_are_removed(client):
    response = client.get("/admin/")
    assert response.status_code == 404
    from django.conf import settings

    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    assert all("AdminTwoFactorGateMiddleware" not in item for item in settings.MIDDLEWARE)


def test_non_owner_cannot_manage_staff(django_user_model):
    sync_admin_roles()
    staff = django_user_model.objects.create_user(
        email="content-staff@example.test",
        password="StrongPassword!2026",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    staff.groups.add(Group.objects.get(name="Content"))
    client = APIClient()
    client.force_login(staff)
    assert client.get("/api/v1/management/users/").status_code == 403
