import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from catalog.models import Category, Product
from landing.models import HeroSlide, SiteSettings


@pytest.mark.django_db
def test_development_seed_is_customer_safe_on_the_public_storefront():
    call_command("seed_synthetic_data")

    public_products = Product.objects.filter(is_active=True, is_sellable=True)
    assert public_products.count() >= 4
    assert not any(
        marker in product.name.lower()
        for product in public_products
        for marker in ("sintét", "sintet", "demo", "prueba")
    )
    assert not Category.objects.filter(is_active=True, name__icontains="sint").exists()
    assert not HeroSlide.objects.filter(enabled=True, title__icontains="sint").exists()
    assert "sint" not in SiteSettings.objects.get(pk=1).announcement.lower()

    category_names = [row["name"] for row in APIClient().get("/api/v1/categories/").json()]
    assert category_names[0] == "Librería"
    assert category_names.index("Cuadernos") < category_names.index("Rayados")
