from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Category, Product
from commerce.models import Coupon, PromotionRule
from landing.models import HeroSlide, PromotionPopup

pytestmark = pytest.mark.django_db


def management_client(django_user_model):
    owner = django_user_model.objects.create_superuser(
        email="content-owner@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(owner)
    return client, owner


def test_management_landing_content_crud_controls_schedule_height_and_popup(django_user_model):
    client, owner = management_client(django_user_model)
    created = client.post(
        "/api/v1/management/content/hero/",
        {
            "title": "Vuelta al cole",
            "body": "Todo para empezar el año",
            "enabled": True,
            "order": 1,
            "cta_label": "Comprar ahora",
            "cta_url": "/catalogo",
            "focal_x": "60.00",
            "focal_y": "45.00",
            "safe_height_mobile": 360,
            "safe_height_tablet": 460,
            "safe_height_desktop": 620,
            "interval_ms": 5500,
            "pause_on_reduced_motion": True,
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["safe_height_desktop"] == 620
    hero = HeroSlide.objects.get()

    updated = client.patch(
        f"/api/v1/management/content/hero/{hero.pk}/",
        {"enabled": False, "order": 3},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    popup = client.post(
        "/api/v1/management/content/popups/",
        {
            "title": "Oferta especial",
            "body": "20% en productos seleccionados",
            "enabled": True,
            "order": 0,
            "frequency": "daily",
            "display_delay_ms": 1200,
            "dismissible": True,
            "version": 2,
        },
        format="json",
    )
    assert popup.status_code == 201
    assert PromotionPopup.objects.get().frequency == "daily"
    assert owner.management_audit_events.filter(resource="landing_content").count() == 3


def test_management_site_settings_exposes_branding_controls(django_user_model):
    client, _ = management_client(django_user_model)
    response = client.get("/api/v1/management/settings/general/")

    assert response.status_code == 200
    assert "logo_url" in response.json()
    assert "favicon_url" in response.json()
    assert response.json()["logo_url"].startswith("/brand/")


def test_management_promotions_and_coupons_cover_scope_and_schedule(django_user_model):
    client, owner = management_client(django_user_model)
    category = Category.objects.create(name="Librería", slug="libreria")
    product = Product.objects.create(
        name="Cuaderno",
        slug="cuaderno",
        category=category,
        is_active=True,
        is_sellable=False,
    )
    now = timezone.now()
    promotion = client.post(
        "/api/v1/management/promotions/rules/",
        {
            "name": "Semana de librería",
            "discount_type": "percentage",
            "value": "15.00",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=7)).isoformat(),
            "enabled": True,
            "product_ids": [product.pk],
            "category_ids": [category.pk],
        },
        format="json",
    )
    assert promotion.status_code == 201
    rule = PromotionRule.objects.get()
    assert list(rule.products.values_list("pk", flat=True)) == [product.pk]

    coupon = client.post(
        "/api/v1/management/promotions/coupons/",
        {
            "code": "vuelta20",
            "discount_type": "percentage",
            "value": "20.00",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=3)).isoformat(),
            "enabled": True,
            "combinable": False,
        },
        format="json",
    )
    assert coupon.status_code == 201
    assert Coupon.objects.get().code == "VUELTA20"
    assert owner.management_audit_events.filter(resource="promotion").count() == 2


def test_customer_cannot_manage_content(django_user_model):
    customer = django_user_model.objects.create_user(
        email="content-customer@example.test",
        password="StrongPassword!2026",
        email_verified_at=timezone.now(),
    )
    client = APIClient()
    client.force_login(customer)
    assert client.get("/api/v1/management/content/hero/").status_code == 403
    assert client.get("/api/v1/management/promotions/rules/").status_code == 403
