from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


def variant_values(**overrides):
    values = {
        "name": "Unica",
        "price": Decimal("1000.00"),
        "cost": Decimal("500.00"),
        "packaged_weight_grams": 100,
        "length_cm": Decimal("10.00"),
        "width_cm": Decimal("10.00"),
        "height_cm": Decimal("5.00"),
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_product_and_variant_skus_are_allocated_in_sequence():
    from catalog.models import Category, Product, ProductVariant

    category = Category.objects.create(name="Papeleria SKU", slug="papeleria-sku")
    first = Product.objects.create(category=category, name="Primero", slug="primero-sku")
    second = Product.objects.create(category=category, name="Segundo", slug="segundo-sku")

    first_variant = ProductVariant.objects.create(product=first, **variant_values())
    second_variant = ProductVariant.objects.create(
        product=first,
        **variant_values(name="Segunda"),
    )

    assert (first.sku, second.sku) == ("600001", "600002")
    assert (first_variant.sku, second_variant.sku) == ("600001-01", "600001-02")


@pytest.mark.django_db
def test_assigned_product_and_variant_skus_cannot_be_changed():
    from catalog.models import Category, Product, ProductVariant

    category = Category.objects.create(name="Inmutables", slug="inmutables-sku")
    product = Product.objects.create(category=category, name="Inmutable", slug="inmutable-sku")
    variant = ProductVariant.objects.create(product=product, **variant_values())

    product.sku = "699999"
    with pytest.raises(ValidationError, match="SKU de un producto no se puede modificar"):
        product.save()

    variant.sku = "699999-99"
    with pytest.raises(ValidationError, match="SKU de una variante no se puede modificar"):
        variant.save()


@pytest.mark.django_db
def test_deleted_sku_numbers_are_not_reused():
    from catalog.models import Category, Product, ProductVariant

    category = Category.objects.create(name="Bajas", slug="bajas-sku")
    first_product = Product.objects.create(category=category, name="Primero", slug="baja-uno")
    first_variant = ProductVariant.objects.create(product=first_product, **variant_values())
    first_variant.delete()
    second_variant = ProductVariant.objects.create(product=first_product, **variant_values())
    first_product.delete()
    second_product = Product.objects.create(category=category, name="Segundo", slug="baja-dos")

    assert second_variant.sku == "600001-02"
    assert second_product.sku == "600002"


@pytest.mark.django_db
def test_product_and_variant_ranges_fail_without_partial_records():
    from catalog.models import CatalogSkuSequence, Category, Product, ProductVariant

    category = Category.objects.create(name="Limites", slug="limites-sku")
    CatalogSkuSequence.objects.filter(key="product").update(next_value=699999)
    last_product = Product.objects.create(category=category, name="Ultimo", slug="ultimo-sku")
    assert last_product.sku == "699999"

    with pytest.raises(ValidationError, match="agotó el rango"):
        Product.objects.create(category=category, name="Excedido", slug="excedido-sku")
    assert not Product.objects.filter(slug="excedido-sku").exists()

    Product.objects.filter(pk=last_product.pk).update(next_variant_sequence=99)
    last_variant = ProductVariant.objects.create(product=last_product, **variant_values())
    assert last_variant.sku == "699999-99"

    with pytest.raises(ValidationError, match="máximo de 99"):
        ProductVariant.objects.create(
            product=last_product,
            **variant_values(name="Excedida"),
        )
    assert last_product.variants.count() == 1


@pytest.mark.django_db
def test_bulk_creation_allocates_product_and_variant_skus_in_input_order():
    from catalog.models import Category, Product, ProductVariant

    category = Category.objects.create(name="Masivos", slug="masivos-sku")
    products = Product.objects.bulk_create(
        [
            Product(category=category, name="Masivo uno", slug="masivo-uno"),
            Product(category=category, name="Masivo dos", slug="masivo-dos"),
        ]
    )
    variants = ProductVariant.objects.bulk_create(
        [
            ProductVariant(product=products[0], **variant_values(name="Primera")),
            ProductVariant(product=products[0], **variant_values(name="Segunda")),
            ProductVariant(product=products[1], **variant_values(name="Unica")),
        ]
    )

    assert [product.sku for product in products] == ["600001", "600002"]
    assert [variant.sku for variant in variants] == [
        "600001-01",
        "600001-02",
        "600002-01",
    ]


@pytest.mark.django_db(transaction=True)
def test_catalog_sku_migration_orders_existing_records_and_avoids_unique_collisions():
    executor = MigrationExecutor(connection)
    executor.migrate([("catalog", "0007_variant_stock_limits")])
    old_apps = executor.loader.project_state([("catalog", "0007_variant_stock_limits")]).apps
    Category = old_apps.get_model("catalog", "Category")
    Product = old_apps.get_model("catalog", "Product")
    ProductVariant = old_apps.get_model("catalog", "ProductVariant")

    category = Category.objects.create(name="Historica", slug="historica-sku")
    newer = Product.objects.create(category=category, name="Nuevo", slug="nuevo-historico")
    older = Product.objects.create(category=category, name="Viejo", slug="viejo-historico")
    Product.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))
    old_first = ProductVariant.objects.create(
        product=older,
        sku="600001-02",
        **variant_values(name="Primera historica"),
    )
    old_second = ProductVariant.objects.create(
        product=older,
        sku="600001-01",
        **variant_values(name="Segunda historica"),
    )
    new_variant = ProductVariant.objects.create(
        product=newer,
        sku="SKU-LEGACY",
        **variant_values(name="Nueva historica"),
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("catalog", "0008_automatic_catalog_skus")])
    new_apps = executor.loader.project_state([("catalog", "0008_automatic_catalog_skus")]).apps
    MigratedProduct = new_apps.get_model("catalog", "Product")
    MigratedVariant = new_apps.get_model("catalog", "ProductVariant")
    CatalogSkuSequence = new_apps.get_model("catalog", "CatalogSkuSequence")

    assert MigratedProduct.objects.get(pk=older.pk).sku == "600001"
    assert MigratedProduct.objects.get(pk=newer.pk).sku == "600002"
    assert MigratedVariant.objects.get(pk=old_first.pk).sku == "600001-01"
    assert MigratedVariant.objects.get(pk=old_second.pk).sku == "600001-02"
    assert MigratedVariant.objects.get(pk=new_variant.pk).sku == "600002-01"
    assert MigratedProduct.objects.get(pk=older.pk).next_variant_sequence == 3
    assert CatalogSkuSequence.objects.get(key="product").next_value == 600003
