from collections import Counter

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, transaction

PRODUCT_SKU_START = 600001
PRODUCT_SKU_END = 699999
VARIANT_SEQUENCE_END = 99


def reserve_product_skus(count: int, *, using: str = DEFAULT_DB_ALIAS) -> list[str]:
    from catalog.models import CatalogSkuSequence

    if count < 1:
        return []
    with transaction.atomic(using=using):
        sequence = (
            CatalogSkuSequence.objects.using(using).select_for_update().get(key="product")
        )
        value = sequence.next_value
        if value + count - 1 > PRODUCT_SKU_END:
            raise ValidationError({"sku": "Se agotó el rango disponible de SKU de productos."})
        sequence.next_value = value + count
        sequence.save(update_fields=("next_value",))
    return [f"{number:06d}" for number in range(value, value + count)]


def reserve_product_sku(*, using: str = DEFAULT_DB_ALIAS) -> str:
    return reserve_product_skus(1, using=using)[0]


def reserve_variant_skus(
    *, product_ids: list[int], using: str = DEFAULT_DB_ALIAS
) -> list[str]:
    from catalog.models import Product

    if not product_ids:
        return []
    counts = Counter(product_ids)
    with transaction.atomic(using=using):
        products = {
            product.pk: product
            for product in Product._base_manager.using(using)
            .select_for_update()
            .filter(pk__in=sorted(counts))
            .order_by("pk")
        }
        if len(products) != len(counts):
            raise ValidationError({"product": "Uno de los productos no existe."})
        for product_id, count in counts.items():
            product = products[product_id]
            if product.next_variant_sequence + count - 1 > VARIANT_SEQUENCE_END:
                raise ValidationError({"sku": "El producto alcanzó el máximo de 99 variantes."})

        next_values = {
            product_id: product.next_variant_sequence for product_id, product in products.items()
        }
        skus = []
        for product_id in product_ids:
            product = products[product_id]
            value = next_values[product_id]
            skus.append(f"{product.sku}-{value:02d}")
            next_values[product_id] = value + 1
        for product_id, next_value in next_values.items():
            Product._base_manager.using(using).filter(pk=product_id).update(
                next_variant_sequence=next_value
            )
    return skus


def reserve_variant_sku(*, product_id: int, using: str = DEFAULT_DB_ALIAS) -> str:
    return reserve_variant_skus(product_ids=[product_id], using=using)[0]
