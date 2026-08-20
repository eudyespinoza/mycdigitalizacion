from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from catalog.models import AttributeDefinition, AttributeValue, Category, Product, ProductVariant
from catalog.services import activate_product


def make_product(*, category: Category, number: int, on_hand: int = 5) -> Product:
    product = Product.objects.create(
        category=category,
        name=f"Cuaderno rendimiento {number:02d}",
        slug=f"cuaderno-rendimiento-{number:02d}",
        description="Cuaderno rayado para pruebas de búsqueda y paginación.",
    )
    ProductVariant.objects.create(
        product=product,
        sku=f"PERF-{number:03d}",
        price=Decimal("100.00") + number,
        cost=Decimal("50.00"),
        packaged_weight_grams=500,
        length_cm=Decimal("20"),
        width_cm=Decimal("15"),
        height_cm=Decimal("2"),
        on_hand=on_hand,
    )
    return activate_product(product=product)


@pytest.mark.django_db
def test_catalog_candidate_queryset_uses_exists_for_stock_and_typed_attributes():
    from catalog.storefront import catalog_candidate_queryset

    category = Category.objects.create(name="Cuadernos", slug="cuadernos")
    product = make_product(category=category, number=1)
    definition = AttributeDefinition.objects.create(
        name="Hojas", slug="hojas", value_type="integer", is_filterable=True
    )
    AttributeValue.objects.create(
        variant=product.variants.get(), definition=definition, integer_value=80
    )

    queryset = catalog_candidate_queryset(
        params={
            "query": "",
            "category": "cuadernos",
            "brand": "",
            "availability": "in_stock",
            "ordering": "newest",
        },
        attribute_filters={"hojas": 80},
    )
    sql = str(queryset.query).upper()

    assert "EXISTS" in sql
    assert "STOCKRESERVATION" in sql
    assert "ATTRIBUTEVALUE" in sql
    assert list(queryset.values_list("pk", flat=True)) == [product.pk]


@pytest.mark.django_db
def test_catalog_page_query_count_is_constant_for_many_products(client):
    category = Category.objects.create(name="Librería", slug="libreria")
    for number in range(18):
        make_product(category=category, number=number)

    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/v1/products/?page=2&page_size=5&ordering=newest")

    assert response.status_code == 200
    assert response.json()["count"] == 18
    assert len(response.json()["results"]) == 5
    assert len(captured) <= 12


@pytest.mark.django_db
@pytest.mark.postgresql
def test_postgres_catalog_search_is_tolerant_and_keeps_the_public_envelope(client):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL fuzzy-search contract")
    category = Category.objects.create(name="Papelería", slug="papeleria")
    product = make_product(category=category, number=91)

    response = client.get("/api/v1/search/?q=Cuaderno%20rendiminto&page_size=5")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["id"] == product.pk
    assert set(response.json()) == {"count", "next", "previous", "results", "facets"}
