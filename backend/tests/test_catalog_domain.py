from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_category_rejects_a_sixth_level():
    from catalog.models import Category

    parent = None
    for level in range(1, 6):
        parent = Category.objects.create(
            name=f"Nivel {level}", slug=f"nivel-{level}", parent=parent
        )

    too_deep = Category(name="Nivel 6", slug="nivel-6", parent=parent)

    with pytest.raises(ValidationError, match="five levels"):
        too_deep.full_clean()


@pytest.mark.django_db
def test_variant_derives_packaged_volume_in_cubic_centimeters():
    from catalog.models import Category, Product, ProductVariant

    category = Category.objects.create(name="Sintetico", slug="sintetico")
    product = Product.objects.create(
        category=category, name="Producto sintetico", slug="producto-sintetico"
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku="SYN-001",
        price=Decimal("100.00"),
        cost=Decimal("40.00"),
        packaged_weight_grams=500,
        length_cm=Decimal("10.00"),
        width_cm=Decimal("5.00"),
        height_cm=Decimal("4.00"),
    )

    assert variant.volume_cm3 == Decimal("200.000000")


@pytest.mark.django_db
def test_product_cannot_be_marked_sellable_without_a_variant():
    from catalog.models import Category, Product

    category = Category.objects.create(name="Sin variante", slug="sin-variante")

    with pytest.raises(ValidationError, match="active variant"):
        Product.objects.create(
            category=category,
            name="Producto incompleto",
            slug="producto-incompleto",
            is_sellable=True,
        )
