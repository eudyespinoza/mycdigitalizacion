import io
import json

import pytest
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Profile
from support.models import SupportAttachment, SupportCase, SupportMessage

pytestmark = pytest.mark.django_db


def guest_payload(**overrides):
    payload = {
        "kind": "consultation",
        "subject": "Consulta por cuadernos",
        "category": "productos",
        "contact_name": "Invitada",
        "contact_email": "invitada@example.test",
        "body": "Necesito ayuda con mi compra.",
        "idempotency_key": "guest-create-1",
    }
    payload.update(overrides)
    return payload


def payload_without_contact_fields(**overrides):
    payload = guest_payload(**overrides)
    payload.pop("contact_name")
    payload.pop("contact_email")
    return payload


def png_upload(name="captura.png"):
    image = Image.new("RGB", (24, 16), "red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def guest_case_and_code():
    case = SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Consulta recuperable",
        category="productos",
        contact_email="invitada@example.test",
        recovery_code_hash=make_password("private-code"),
    )
    return case, "private-code"


def test_configuration_exposes_public_categories_limits_and_authentication(api_client):
    response = api_client.get("/api/v1/support/configuration/")

    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert response.json()["email_available"] is False
    assert response.json()["categories"]["consultation"] == [
        "productos",
        "compra",
        "envios",
        "pagos",
        "facturacion",
        "otra",
    ]
    assert response.json()["limits"] == {
        "max_files": 5,
        "max_file_size_bytes": 10 * 1024 * 1024,
        "max_total_size_bytes": 30 * 1024 * 1024,
    }


def test_guest_creates_case_continues_with_secure_cookie_and_only_sees_own_case(api_client):
    response = api_client.post("/api/v1/support/cases/", guest_payload(), format="multipart")

    assert response.status_code == 201
    payload = response.json()
    assert payload["recovery_code"]
    assert "myc_support_session" not in response.content.decode()
    cookie = response.cookies["myc_support_session"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
    assert not cookie["secure"]

    listed = api_client.get("/api/v1/support/cases/")
    assert listed.status_code == 200
    assert listed.json()["results"][0]["public_id"] == payload["public_id"]
    assert "recovery_code" not in listed.json()["results"][0]

    other_client = APIClient()
    assert other_client.get(f"/api/v1/support/cases/{payload['public_id']}/").status_code == 404


def test_case_creation_idempotency_never_reveals_recovery_code_on_a_later_retry(api_client):
    first = api_client.post("/api/v1/support/cases/", guest_payload(), format="multipart")
    retry = api_client.post("/api/v1/support/cases/", guest_payload(), format="multipart")

    assert first.status_code == retry.status_code == 201
    assert first.json()["public_id"] == retry.json()["public_id"]
    assert first.json()["recovery_code"]
    assert "recovery_code" not in retry.json()


def test_recovery_requires_number_and_private_code_and_links_this_session(
    api_client, guest_case_and_code
):
    case, code = guest_case_and_code

    denied = api_client.post(
        "/api/v1/support/access/",
        {"case_number": case.case_number, "code": "wrong"},
        format="json",
    )
    allowed = api_client.post(
        "/api/v1/support/access/",
        {"case_number": case.case_number, "code": code},
        format="json",
    )

    assert denied.status_code == 400
    assert allowed.status_code == 200
    assert api_client.get(f"/api/v1/support/cases/{case.public_id}/").status_code == 200


def test_authenticated_creation_derives_contact_snapshot_without_contact_fields(
    api_client, django_user_model
):
    customer = django_user_model.objects.create_user("ada@example.test", password="password")
    Profile.objects.create(user=customer, first_name="Ada", last_name="Lovelace")
    api_client.force_login(customer)

    response = api_client.post(
        "/api/v1/support/cases/",
        payload_without_contact_fields(idempotency_key="authenticated-create-1"),
        format="multipart",
    )

    assert response.status_code == 201
    created = SupportCase.objects.get(public_id=response.json()["public_id"])
    assert created.contact_name == "Ada Lovelace"
    assert created.contact_email == "ada@example.test"


def test_authenticated_creation_cannot_spoof_contact_snapshot(api_client, django_user_model):
    customer = django_user_model.objects.create_user("real@example.test", password="password")
    Profile.objects.create(user=customer, first_name="Nombre", last_name="Real")
    api_client.force_login(customer)

    response = api_client.post(
        "/api/v1/support/cases/",
        guest_payload(
            contact_name="Nombre impostor",
            contact_email="impostor@example.test",
            idempotency_key="authenticated-create-2",
        ),
        format="multipart",
    )

    assert response.status_code == 201
    created = SupportCase.objects.get(public_id=response.json()["public_id"])
    assert created.contact_name == "Nombre Real"
    assert created.contact_email == "real@example.test"


def test_authenticated_creation_ignores_malformed_contact_values_before_field_validation(
    api_client, django_user_model
):
    customer = django_user_model.objects.create_user("safe@example.test", password="password")
    Profile.objects.create(user=customer, first_name="Cuenta", last_name="Segura")
    api_client.force_login(customer)

    response = api_client.post(
        "/api/v1/support/cases/",
        guest_payload(
            contact_name="x" * 181,
            contact_email="no-es-un-correo",
            idempotency_key="authenticated-create-malformed-contact",
        ),
        format="multipart",
    )

    assert response.status_code == 201
    created = SupportCase.objects.get(public_id=response.json()["public_id"])
    assert created.contact_name == "Cuenta Segura"
    assert created.contact_email == "safe@example.test"


def test_guest_creation_rejects_malformed_contact_values(api_client):
    response = api_client.post(
        "/api/v1/support/cases/",
        guest_payload(
            contact_name="x" * 181,
            contact_email="no-es-un-correo",
            idempotency_key="guest-create-malformed-contact",
        ),
        format="multipart",
    )

    assert response.status_code == 400
    assert {"contact_name", "contact_email"} <= response.json().keys()


def test_guest_creation_requires_contact_fields_with_spanish_errors(api_client):
    response = api_client.post(
        "/api/v1/support/cases/",
        payload_without_contact_fields(idempotency_key="guest-missing-contact"),
        format="multipart",
    )

    assert response.status_code == 400
    assert response.json()["contact_name"] == ["El nombre de contacto es obligatorio."]
    assert response.json()["contact_email"] == ["El correo electrónico de contacto es obligatorio."]


def test_authenticated_creation_without_account_email_returns_spanish_validation_error(
    api_client, django_user_model
):
    customer = django_user_model(email="")
    customer.set_password("password")
    customer.save()
    api_client.force_login(customer)

    response = api_client.post(
        "/api/v1/support/cases/",
        payload_without_contact_fields(idempotency_key="authenticated-create-no-email"),
        format="multipart",
    )

    assert response.status_code == 400
    assert response.json()["contact_email"] == [
        "Tu cuenta no tiene un correo electrónico válido para crear el caso."
    ]


def test_authenticated_customer_only_sees_own_cases_and_claim_requires_code(
    api_client, django_user_model, guest_case_and_code
):
    customer = django_user_model.objects.create_user("customer@example.test", password="password")
    other = django_user_model.objects.create_user("other@example.test", password="password")
    owned = SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Propio",
        category="productos",
        customer=customer,
        recovery_code_hash=make_password("owned-code"),
    )
    recoverable, code = guest_case_and_code
    api_client.force_login(customer)

    listed = api_client.get("/api/v1/support/cases/")
    assert [item["public_id"] for item in listed.json()["results"]] == [str(owned.public_id)]
    assert api_client.get(f"/api/v1/support/cases/{recoverable.public_id}/").status_code == 404
    assert (
        api_client.post(
            f"/api/v1/support/cases/{recoverable.public_id}/claim/",
            {"code": "wrong"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        api_client.post(
            f"/api/v1/support/cases/{recoverable.public_id}/claim/", {"code": code}, format="json"
        ).status_code
        == 200
    )

    other_client = APIClient()
    other_client.force_login(other)
    assert other_client.get(f"/api/v1/support/cases/{recoverable.public_id}/").status_code == 404


def test_authenticated_guest_session_keeps_only_its_linked_cases(api_client, django_user_model):
    created = api_client.post("/api/v1/support/cases/", guest_payload(), format="multipart")
    guest_case_id = created.json()["public_id"]
    owner = django_user_model.objects.create_user("owner@example.test", password="password")
    unrelated = django_user_model.objects.create_user(
        "unrelated@example.test", password="password"
    )
    owned = SupportCase.objects.create(
        kind=SupportCase.Kind.CONSULTATION,
        subject="Caso propio",
        category="productos",
        customer=owner,
        recovery_code_hash=make_password("owned-code"),
    )

    api_client.force_login(unrelated)
    listed = api_client.get("/api/v1/support/cases/")

    assert listed.status_code == 200
    assert [item["public_id"] for item in listed.json()["results"]] == [guest_case_id]
    assert api_client.get(f"/api/v1/support/cases/{guest_case_id}/").status_code == 200

    owner_client = APIClient()
    owner_client.force_login(owner)
    assert [item["public_id"] for item in owner_client.get("/api/v1/support/cases/").json()[
        "results"
    ]] == [str(owned.public_id)]
    assert owner_client.get(f"/api/v1/support/cases/{guest_case_id}/").status_code == 404


def test_message_uses_case_access_and_private_downloads_do_not_leak(api_client, settings, tmp_path):
    settings.SUPPORT_PRIVATE_MEDIA_ROOT = tmp_path
    created = api_client.post(
        "/api/v1/support/cases/",
        guest_payload(attachments=[png_upload()]),
        format="multipart",
    )
    case_id = created.json()["public_id"]
    attachment = SupportAttachment.objects.get()

    message = api_client.post(
        f"/api/v1/support/cases/{case_id}/messages/",
        {"body": "Agrego información.", "idempotency_key": "message-1"},
        format="multipart",
    )
    assert message.status_code == 201
    assert SupportMessage.objects.filter(case__public_id=case_id).count() == 2

    other_client = APIClient()
    assert (
        other_client.get(f"/api/v1/support/attachments/{attachment.public_id}/").status_code == 404
    )

    original = api_client.get(f"/api/v1/support/attachments/{attachment.public_id}/")
    preview = api_client.get(f"/api/v1/support/attachments/{attachment.public_id}/?preview=1")
    assert original.status_code == preview.status_code == 200
    assert original["Content-Disposition"].startswith("attachment;")
    assert original["X-Content-Type-Options"] == "nosniff"
    assert preview["Content-Type"].startswith("image/webp")
    assert preview["Content-Disposition"].startswith("inline;")


def test_source_url_is_reduced_to_same_site_path(api_client):
    response = api_client.post(
        "/api/v1/support/cases/",
        guest_payload(source_url="https://testserver/productos/cuaderno?token=secret#private"),
        format="multipart",
    )

    assert response.status_code == 201
    assert SupportCase.objects.get().source_url == "/productos/cuaderno"


def test_openapi_documents_the_public_support_routes_and_one_time_recovery_code(api_client):
    schema = json.loads(api_client.get("/api/v1/schema/?format=json").content)
    paths = schema["paths"]

    assert {
        "/api/v1/support/configuration/",
        "/api/v1/support/cases/",
        "/api/v1/support/cases/{public_id}/",
        "/api/v1/support/cases/{public_id}/messages/",
        "/api/v1/support/cases/{public_id}/claim/",
        "/api/v1/support/access/",
        "/api/v1/support/attachments/{public_id}/",
    } <= paths.keys()
    created = paths["/api/v1/support/cases/"]["post"]["responses"]["201"]["content"][
        "application/json"
    ]["schema"]
    component_name = created["$ref"].rsplit("/", 1)[-1]
    assert "recovery_code" in schema["components"]["schemas"][component_name]["properties"]
