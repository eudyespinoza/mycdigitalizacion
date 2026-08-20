from decimal import Decimal

import pytest
from django.core.cache import cache
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db


def test_committed_catalog_changes_advance_the_cache_version(
    django_capture_on_commit_callbacks,
):
    from catalog.cache import catalog_cache_version

    with django_capture_on_commit_callbacks(execute=True):
        category = Category.objects.create(name="Caché", slug="cache")
    cache.clear()
    before = catalog_cache_version()
    with django_capture_on_commit_callbacks(execute=True):
        product = Product.objects.create(
            category=category,
            name="Producto cacheado",
            slug="producto-cacheado",
        )

    assert catalog_cache_version() == before + 1

    with django_capture_on_commit_callbacks(execute=True):
        ProductVariant.objects.create(
            product=product,
            sku="CACHE-001",
            price=Decimal("100.00"),
            cost=Decimal("50.00"),
            packaged_weight_grams=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("2"),
            on_hand=1,
        )

    assert catalog_cache_version() == before + 2


def test_catalog_cache_keys_are_stable_for_equivalent_filter_orderings():
    from catalog.cache import catalog_cache_key

    first = catalog_cache_key("facets", {"brand": ["myc", "acme"], "page": 1})
    second = catalog_cache_key("facets", {"page": 1, "brand": ["myc", "acme"]})

    assert first == second


def test_catalog_changes_inside_one_transaction_invalidate_once(
    django_capture_on_commit_callbacks,
):
    from catalog.cache import catalog_cache_version

    cache.clear()
    before = catalog_cache_version()
    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            Category.objects.create(name="Uno", slug="uno")
            Category.objects.create(name="Dos", slug="dos")

    assert catalog_cache_version() == before + 1


def test_public_categories_are_cached_and_invalidated(
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(execute=True):
        Category.objects.create(name="Inicial", slug="inicial")
    cache.clear()
    client = APIClient()
    assert client.get("/api/v1/categories/").status_code == 200

    with CaptureQueriesContext(connection) as captured:
        cached = client.get("/api/v1/categories/")
    assert cached.status_code == 200
    assert len(captured) == 0

    with django_capture_on_commit_callbacks(execute=True):
        Category.objects.create(name="Nueva", slug="nueva")
    refreshed = client.get("/api/v1/categories/")
    assert {row["slug"] for row in refreshed.json()} == {"inicial", "nueva"}
