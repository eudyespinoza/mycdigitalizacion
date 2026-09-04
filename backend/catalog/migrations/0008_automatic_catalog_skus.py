import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations, models

PRODUCT_SKU_START = 600001
PRODUCT_SKU_END = 699999
VARIANT_SEQUENCE_END = 99


def assign_catalog_skus(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    CatalogSkuSequence = apps.get_model("catalog", "CatalogSkuSequence")
    database = schema_editor.connection.alias

    products = list(Product.objects.using(database).order_by("created_at", "id"))
    if PRODUCT_SKU_START + len(products) - 1 > PRODUCT_SKU_END:
        raise RuntimeError("El catálogo supera el rango disponible de SKU de productos.")

    for variant_id in ProductVariant.objects.using(database).values_list("id", flat=True):
        ProductVariant.objects.using(database).filter(pk=variant_id).update(
            sku=f"__sku_tmp_{variant_id}"
        )

    next_product_number = PRODUCT_SKU_START
    for product in products:
        product_sku = f"{next_product_number:06d}"
        Product.objects.using(database).filter(pk=product.pk).update(sku=product_sku)
        variant_ids = list(
            ProductVariant.objects.using(database)
            .filter(product_id=product.pk)
            .order_by("id")
            .values_list("id", flat=True)
        )
        if len(variant_ids) > VARIANT_SEQUENCE_END:
            raise RuntimeError(
                f"El producto {product.pk} supera el máximo de 99 variantes."
            )
        for suffix, variant_id in enumerate(variant_ids, start=1):
            ProductVariant.objects.using(database).filter(pk=variant_id).update(
                sku=f"{product_sku}-{suffix:02d}"
            )
        Product.objects.using(database).filter(pk=product.pk).update(
            next_variant_sequence=len(variant_ids) + 1
        )
        next_product_number += 1

    CatalogSkuSequence.objects.using(database).update_or_create(
        key="product",
        defaults={"next_value": next_product_number},
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("catalog", "0007_variant_stock_limits")]

    operations = [
        migrations.CreateModel(
            name="CatalogSkuSequence",
            fields=[
                ("key", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("next_value", models.PositiveIntegerField()),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="product",
                    name="cat_prod_search_gin",
                ),
                migrations.RemoveIndex(
                    model_name="product",
                    name="cat_prod_name_trgm",
                ),
                migrations.RemoveIndex(
                    model_name="productvariant",
                    name="cat_variant_sku_trgm",
                ),
            ],
        ),
        migrations.AddField(
            model_name="product",
            name="next_variant_sequence",
            field=models.PositiveSmallIntegerField(db_default=1, default=1, editable=False),
        ),
        migrations.AddField(
            model_name="product",
            name="sku",
            field=models.CharField(max_length=6, null=True, unique=True),
        ),
        migrations.RunPython(
            assign_catalog_skus,
            migrations.RunPython.noop,
            atomic=True,
        ),
        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(
                editable=False,
                max_length=6,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="sku",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddIndex(
                    model_name="product",
                    index=django.contrib.postgres.indexes.GinIndex(
                        django.contrib.postgres.search.SearchVector(
                            "name", "description", config="spanish"
                        ),
                        name="cat_prod_search_gin",
                    ),
                ),
                migrations.AddIndex(
                    model_name="product",
                    index=django.contrib.postgres.indexes.GinIndex(
                        fields=["name"],
                        name="cat_prod_name_trgm",
                        opclasses=("gin_trgm_ops",),
                    ),
                ),
                migrations.AddIndex(
                    model_name="productvariant",
                    index=django.contrib.postgres.indexes.GinIndex(
                        fields=["sku"],
                        name="cat_variant_sku_trgm",
                        opclasses=("gin_trgm_ops",),
                    ),
                ),
            ],
        ),
    ]
