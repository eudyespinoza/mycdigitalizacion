from dataclasses import replace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.arca_a13 import ArcaPerson, ArcaUnavailableError
from accounts.fiscal_identity import FiscalIdentityError, resolve_fiscal_identifier
from accounts.models import BillingProfile


class FakeArcaAdapter:
    def __init__(self, *, ids=None, person=None, error=None):
        self.ids = ids or []
        self.person = person or ArcaPerson(
            id_persona="20123456786",
            numero_documento="12345678",
            estado_clave="ACTIVO",
        )
        self.error = error
        self.document_calls = []
        self.person_calls = []

    def get_id_persona_list_by_documento(self, documento):
        self.document_calls.append(documento)
        if self.error:
            raise self.error
        return self.ids

    def get_persona(self, cuit):
        self.person_calls.append(cuit)
        if self.error:
            raise self.error
        return self.person


def test_full_cuit_skips_document_resolution(monkeypatch):
    adapter = FakeArcaAdapter()
    monkeypatch.setattr(
        "accounts.fiscal_identity.get_arca_a13_client", lambda: adapter
    )

    assert resolve_fiscal_identifier("20-12345678-6") == "20123456786"
    assert adapter.document_calls == []
    assert adapter.person_calls == ["20123456786"]


def test_dni_resolves_cuit_before_getting_person(monkeypatch):
    adapter = FakeArcaAdapter(ids=["20123456786"])
    monkeypatch.setattr(
        "accounts.fiscal_identity.get_arca_a13_client", lambda: adapter
    )

    assert resolve_fiscal_identifier("12.345.678") == "20123456786"
    assert adapter.document_calls == ["12345678"]
    assert adapter.person_calls == ["20123456786"]


@pytest.mark.parametrize("value", ["123456", "123456789", "1234567890", "123456789012"])
def test_identifier_length_must_be_dni_or_cuit(monkeypatch, value):
    monkeypatch.setattr("accounts.fiscal_identity.get_arca_a13_client", lambda: None)

    with pytest.raises(FiscalIdentityError, match="7 u 8 dígitos"):
        resolve_fiscal_identifier(value)


def test_disabled_integration_accepts_full_cuit_but_requires_it_for_dni(monkeypatch):
    monkeypatch.setattr("accounts.fiscal_identity.get_arca_a13_client", lambda: None)

    assert resolve_fiscal_identifier("20123456786") == "20123456786"
    with pytest.raises(FiscalIdentityError, match="CUIT completo"):
        resolve_fiscal_identifier("12345678")


@pytest.mark.parametrize(
    ("adapter", "value", "message"),
    [
        (FakeArcaAdapter(ids=[]), "12345678", "CUIT asociado"),
        (
            FakeArcaAdapter(ids=["20123456786", "20329642330"]),
            "12345678",
            "más de un CUIT",
        ),
        (
            FakeArcaAdapter(
                ids=["20123456786"],
                person=ArcaPerson("20123456786", "87654321", "ACTIVO"),
            ),
            "12345678",
            "documento informado",
        ),
        (
            FakeArcaAdapter(
                person=replace(
                    FakeArcaAdapter().person,
                    estado_clave="INACTIVO",
                )
            ),
            "20123456786",
            "no está activo",
        ),
    ],
)
def test_arca_rejects_ambiguous_or_mismatched_identity(
    monkeypatch, adapter, value, message
):
    monkeypatch.setattr(
        "accounts.fiscal_identity.get_arca_a13_client", lambda: adapter
    )
    with pytest.raises(FiscalIdentityError, match=message):
        resolve_fiscal_identifier(value)


@pytest.mark.django_db
def test_provider_outage_returns_retryable_error_without_persisting(monkeypatch, django_user_model):
    adapter = FakeArcaAdapter(error=ArcaUnavailableError("private diagnostics"))
    monkeypatch.setattr(
        "accounts.fiscal_identity.get_arca_a13_client", lambda: adapter
    )
    user = django_user_model.objects.create_user(
        email="fiscal@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(user)

    response = client.post(
        "/api/v1/billing-profiles/",
        {
            "label": "Compras",
            "legal_name": "Cliente Fiscal",
            "tax_condition": "consumidor_final",
            "cuit": "20123456786",
            "is_default": True,
        },
        format="json",
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "fiscal_identity_unavailable",
        "detail": "No pudimos validar los datos con ARCA. Intentá nuevamente.",
    }
    assert not BillingProfile.objects.filter(customer__user=user).exists()
