import re
import uuid
from io import BytesIO

import pytest
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from tests.test_task3_round2_regressions import eligible_shipping_order


def one_page_pdf(color):
    output = BytesIO()
    Image.new("RGB", (20, 20), color=color).save(output, format="PDF")
    return output.getvalue()


def shipment_with_parcels(order, *, statuses):
    from commerce.models import Shipment, ShipmentParcelImport

    shipment = Shipment.objects.create(
        order=order,
        provider="andreani",
        provider_id=f"shipment-{uuid.uuid4()}",
        tracking_number="tracking-1",
        status=("imported" if all(status == "imported" for status in statuses) else "importing"),
    )
    for index, parcel_status in enumerate(statuses, start=1):
        ShipmentParcelImport.objects.create(
            shipment=shipment,
            parcel_index=index,
            external_id=f"parcel-{uuid.uuid4()}",
            idempotency_key=uuid.uuid4(),
            parcel_snapshot={"weight_grams": 1000},
            status=parcel_status,
            provider_id=f"andreani-{index}",
        )
    return shipment


@pytest.mark.django_db
def test_staff_downloads_one_combined_internal_pdf_in_parcel_order(
    django_user_model, monkeypatch
):
    order = eligible_shipping_order(django_user_model, parcel_count=2, provider="andreani")
    shipment = shipment_with_parcels(order, statuses=["imported", "imported"])
    staff = django_user_model.objects.create_user(
        email="label-staff@example.test",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(staff)

    class Adapter:
        def __init__(self):
            self.calls = []

        def label(self, provider_id):
            self.calls.append(provider_id)
            return one_page_pdf("red" if provider_id.endswith("1") else "blue")

    adapter = Adapter()
    monkeypatch.setattr("api_views.get_carrier_adapter", lambda provider: adapter)
    url = f"/api/v1/orders/{order.public_id}/label/"

    from backoffice.operations_serializers import ManagementShipmentSerializer

    assert ManagementShipmentSerializer(shipment).data["label_url"] == url

    prepared = client.post(url, format="json")

    assert prepared.status_code == 200
    assert prepared.json() == {"label_url": url}
    assert "andreani.com" not in str(prepared.json())

    downloaded = client.get(url)
    document = b"".join(downloaded.streaming_content)

    assert downloaded.status_code == 200
    assert downloaded.headers["Content-Type"] == "application/pdf"
    assert downloaded.headers["Content-Disposition"] == (
        f'attachment; filename="andreani-{order.public_id}.pdf"'
    )
    assert document.startswith(b"%PDF-")
    assert len(re.findall(br"/Type\s*/Page(?!s)", document)) == 2
    assert adapter.calls == ["andreani-1", "andreani-2"]

    preview = client.get(f"{url}?preview=1")
    preview_document = b"".join(preview.streaming_content)

    assert preview.status_code == 200
    assert preview.headers["Content-Disposition"] == (
        f'inline; filename="andreani-{order.public_id}.pdf"'
    )
    assert len(re.findall(br"/Type\s*/Page(?!s)", preview_document)) == 2


@pytest.mark.django_db
def test_label_download_rejects_pending_parcels_without_calling_andreani(
    django_user_model, monkeypatch
):
    order = eligible_shipping_order(django_user_model, parcel_count=1, provider="andreani")
    shipment = shipment_with_parcels(order, statuses=["submitted"])
    staff = django_user_model.objects.create_user(
        email="pending-label-staff@example.test",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(staff)

    class Adapter:
        def label(self, provider_id):
            raise AssertionError(f"label requested too early for {provider_id}")

    monkeypatch.setattr("api_views.get_carrier_adapter", lambda provider: Adapter())

    from backoffice.operations_serializers import ManagementShipmentSerializer

    assert ManagementShipmentSerializer(shipment).data["label_url"] == ""

    response = client.get(f"/api/v1/orders/{order.public_id}/label/")

    assert response.status_code == 409
    assert response.json()["code"] == "shipment_label_not_ready"


@pytest.mark.django_db
def test_management_label_remains_available_after_tracking_updates_shipment_status(
    django_user_model,
):
    order = eligible_shipping_order(django_user_model, parcel_count=1, provider="andreani")
    shipment = shipment_with_parcels(order, statuses=["imported"])
    shipment.status = "en distribución"
    shipment.save(update_fields=("status",))

    from backoffice.operations_serializers import ManagementShipmentSerializer

    assert ManagementShipmentSerializer(shipment).data["label_url"] == (
        f"/api/v1/orders/{order.public_id}/label/"
    )


@pytest.mark.django_db
def test_customer_cannot_download_an_order_label(django_user_model):
    order = eligible_shipping_order(django_user_model, parcel_count=1, provider="andreani")
    shipment_with_parcels(order, statuses=["imported"])
    client = APIClient()
    client.force_authenticate(order.user)

    response = client.get(f"/api/v1/orders/{order.public_id}/label/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_internal_label_proxy_is_restricted_to_andreani(django_user_model):
    order = eligible_shipping_order(
        django_user_model, parcel_count=1, provider="correo_argentino"
    )
    shipment = shipment_with_parcels(order, statuses=["imported"])
    shipment.provider = "correo_argentino"
    shipment.save(update_fields=("provider",))
    staff = django_user_model.objects.create_user(
        email="unsupported-label-staff@example.test",
        is_staff=True,
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(staff)

    response = client.post(f"/api/v1/orders/{order.public_id}/label/", format="json")

    assert response.status_code == 501
    assert response.json()["code"] == "not_supported"


@pytest.mark.django_db
def test_management_shipment_failure_is_logistics_specific_and_sanitized(
    django_user_model, monkeypatch
):
    from providers import ProviderUnavailable

    order = eligible_shipping_order(django_user_model, parcel_count=1, provider="andreani")
    staff = django_user_model.objects.create_superuser(
        email="shipment-failure-staff@example.test",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(staff)

    class Adapter:
        provider = "andreani"

        def import_shipment(self, payload, *, idempotency_key):
            del payload, idempotency_key
            raise ProviderUnavailable(
                "Andreani unavailable secret-password",
                diagnostics="x-authorization-token=secret-token",
            )

    monkeypatch.setattr(
        "backoffice.operations_views.get_carrier_adapter", lambda provider: Adapter()
    )

    response = client.post(
        f"/api/v1/management/orders/{order.public_id}/actions/",
        {"action": "create_shipment", "reason": "Preparar despacho"},
        format="json",
    )

    assert response.status_code == 503
    assert response.json()["code"] == "shipping_provider_unavailable"
    assert "Mercado Pago" not in str(response.json())
    assert "secret-password" not in str(response.json())
    assert "secret-token" not in str(response.json())


@pytest.mark.django_db
def test_label_proxy_sanitizes_pdf_serialization_failures(django_user_model, monkeypatch):
    from pypdf.errors import PyPdfError

    order = eligible_shipping_order(django_user_model, parcel_count=1, provider="andreani")
    shipment_with_parcels(order, statuses=["imported"])
    staff = django_user_model.objects.create_superuser(
        email="label-pdf-failure@example.test",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(staff)
    client.raise_request_exception = False

    class Adapter:
        def label(self, provider_id):
            del provider_id
            return one_page_pdf("red")

    class FailingWriter:
        def add_page(self, page):
            del page

        def write(self, output):
            del output
            raise PyPdfError("sensitive parser details")

    monkeypatch.setattr("api_views.get_carrier_adapter", lambda provider: Adapter())
    monkeypatch.setattr("api_views.PdfWriter", FailingWriter)

    response = client.get(f"/api/v1/orders/{order.public_id}/label/")

    assert response.status_code == 502
    assert response.json() == {
        "code": "invalid_response",
        "detail": "El servicio externo devolvió una respuesta inválida.",
    }
    assert "sensitive parser details" not in str(response.json())
