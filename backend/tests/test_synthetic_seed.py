import pytest
from django.core.management import call_command

from catalog.models import Product, ProductVariant
from landing.models import HeroSlide


@pytest.mark.django_db
def test_synthetic_seed_is_deterministic_and_explicitly_labeled():
    call_command("seed_synthetic_data")
    call_command("seed_synthetic_data")

    assert Product.objects.filter(slug="producto-sintetico-demo").count() == 1
    assert ProductVariant.objects.filter(sku="SYN-DEMO-001").count() == 1
    assert HeroSlide.objects.get(pk=1).title == "Colección sintética de demostración"
