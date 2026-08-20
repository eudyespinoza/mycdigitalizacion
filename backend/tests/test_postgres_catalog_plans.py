import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from catalog.models import (
    AttributeDefinition,
    AttributeOption,
    Brand,
    Category,
    Product,
    ProductVariant,
)
from commerce.models import Order

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.postgresql]


def explain_index_names(sql: str, params: tuple[object, ...]) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}", params)
        root = cursor.fetchone()[0][0]["Plan"]

    names: set[str] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if node.get("Index Name"):
            names.add(node["Index Name"])
        pending.extend(node.get("Plans", []))
    return names


def test_large_catalog_and_management_queries_use_performance_indexes():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL query plans only")

    prefix = uuid.uuid4().hex[:8]
    categories = [
        Category.objects.create(name=f"Categoría {prefix} {number}", slug=f"cat-{prefix}-{number}")
        for number in range(5)
    ]
    brands = [
        Brand.objects.create(name=f"Marca {prefix} {number}", slug=f"brand-{prefix}-{number}")
        for number in range(5)
    ]
    products = Product.objects.bulk_create(
        [
            Product(
                category=categories[number % 5],
                brand=brands[number % 5],
                name=(
                    "Lapicera ultravioleta zafiro 1999"
                    if number == 1999
                    else f"Producto {prefix} serie {number:04d}"
                ),
                slug=f"product-{prefix}-{number:04d}",
                description=f"codigoespecial{prefix}{number:04d}",
                is_active=True,
                is_sellable=True,
            )
            for number in range(20000)
        ],
        batch_size=500,
    )
    ProductVariant.objects.bulk_create(
        [
            ProductVariant(
                product=product,
                sku=f"SKU-{prefix}-{number:04d}",
                name="Única",
                price=Decimal("100.00"),
                cost=Decimal("50.00"),
                packaged_weight_grams=100,
                length_cm=Decimal("10.00"),
                width_cm=Decimal("10.00"),
                height_cm=Decimal("2.00"),
                on_hand=5,
                is_active=True,
            )
            for number, product in enumerate(products)
        ],
        batch_size=500,
    )

    definition = AttributeDefinition.objects.create(
        name=f"Color {prefix}",
        slug=f"color-{prefix}",
        value_type=AttributeDefinition.ValueType.OPTION,
    )
    options = [
        AttributeOption.objects.create(
            definition=definition,
            label=f"Opción {number}",
            value=f"opcion-{number}",
        )
        for number in range(5)
    ]
    option = options[0]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO catalog_attributevalue
                (variant_id, definition_id, option_id, text_value,
                 integer_value, decimal_value, boolean_value)
                SELECT id, %s,
                       CASE (right(sku, 4)::integer %% 5)
                           WHEN 0 THEN %s WHEN 1 THEN %s WHEN 2 THEN %s
                           WHEN 3 THEN %s ELSE %s
                       END,
                       '', NULL, NULL, NULL
                FROM catalog_productvariant
                WHERE sku LIKE %s
                """,
                (
                    definition.pk,
                    *(item.pk for item in options),
                    f"SKU-{prefix}-%",
                ),
        )

    user_model = get_user_model()
    operator = user_model.objects.create_user(email=f"operator-{prefix}@example.test")
    user_model.objects.bulk_create(
        [
            user_model(
                email=f"customer-{prefix}-{number:04d}@example.test",
                password="!",
            )
            for number in range(20000)
        ],
        batch_size=500,
    )
    payment_statuses = (
        Order.PaymentStatus.PENDING,
        Order.PaymentStatus.PAID,
        Order.PaymentStatus.FAILED,
        Order.PaymentStatus.NEEDS_ATTENTION,
        Order.PaymentStatus.NOT_STARTED,
    )
    Order.objects.bulk_create(
        [
            Order(
                user=operator,
                fulfillment_method=Order.FulfillmentMethod.PICKUP,
                identity_status=Order.IdentityStatus.VERIFIED,
                payment_status=payment_statuses[number % len(payment_statuses)],
                fulfillment_status=Order.FulfillmentStatus.UNFULFILLED,
                customer_snapshot={},
                address_snapshot={},
                fiscal_snapshot={},
                subtotal_snapshot=Decimal("100.00"),
                discount_snapshot=Decimal("0.00"),
                total_snapshot=Decimal("100.00"),
            )
            for number in range(3500)
        ],
        batch_size=500,
    )

    with connection.cursor() as cursor:
        for table in (
            "catalog_product",
            "catalog_productvariant",
            "catalog_attributevalue",
            "accounts_user",
            "commerce_order",
        ):
            cursor.execute(f'VACUUM (ANALYZE) "{table}"')

    assert "cat_prod_live_cat_idx" in explain_index_names(
        """
        SELECT id FROM catalog_product
        WHERE category_id = %s AND is_active AND is_sellable
        ORDER BY created_at DESC, id DESC LIMIT 24
        """,
        (categories[0].pk,),
    )
    assert "cat_prod_live_brand_idx" in explain_index_names(
        """
        SELECT id FROM catalog_product
        WHERE brand_id = %s AND is_active AND is_sellable
        ORDER BY created_at DESC, id DESC LIMIT 24
        """,
        (brands[1].pk,),
    )
    assert "cat_prod_search_gin" in explain_index_names(
        """
        SELECT id FROM catalog_product
        WHERE to_tsvector('spanish', coalesce(name, '') || ' ' || coalesce(description, ''))
              @@ plainto_tsquery('spanish', %s)
        """,
        (f"codigoespecial{prefix}1999",),
    )
    assert "cat_prod_name_trgm" in explain_index_names(
        "SELECT id FROM catalog_product WHERE name ILIKE %s",
        ("%ultravioleta zafiro 1999%",),
    )
    assert "cat_variant_sku_trgm" in explain_index_names(
        "SELECT id FROM catalog_productvariant WHERE sku ILIKE %s",
        (f"%{prefix}-1999%",),
    )
    assert "cat_attr_option_idx" in explain_index_names(
        """
        SELECT variant_id FROM catalog_attributevalue
        WHERE definition_id = %s AND option_id = %s
        """,
        (definition.pk, option.pk),
    )
    assert "comm_order_mgmt_idx" in explain_index_names(
        """
        SELECT id FROM commerce_order
        WHERE payment_status = %s AND fulfillment_status = %s
        ORDER BY created_at DESC, id DESC LIMIT 24
        """,
        (Order.PaymentStatus.NEEDS_ATTENTION, Order.FulfillmentStatus.UNFULFILLED),
    )
    assert "acct_user_email_trgm" in explain_index_names(
        "SELECT id FROM accounts_user WHERE email ILIKE %s",
        (f"%{prefix}-1999%",),
    )
