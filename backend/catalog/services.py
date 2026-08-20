from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Category, Product, ProductVariant


def _category_depth(category):
    depth = 0
    current = category
    seen = set()
    while current:
        if current.pk in seen:
            raise ValidationError("Category move would create a cycle")
        seen.add(current.pk)
        depth += 1
        current = current.parent
    return depth


def _subtree_height(category):
    children = list(category.children.all())
    return 1 if not children else 1 + max(_subtree_height(child) for child in children)


@transaction.atomic
def move_category(*, category, new_parent):
    locked = Category.objects.select_for_update().get(pk=category.pk)
    parent = (
        Category.objects.select_for_update().get(pk=new_parent.pk) if new_parent else None
    )
    descendant_ids = set()
    frontier = [locked.pk]
    while frontier:
        descendant_ids.update(frontier)
        frontier = list(
            Category.objects.select_for_update()
            .filter(parent_id__in=frontier)
            .values_list("pk", flat=True)
        )
    if parent and parent.pk in descendant_ids:
        raise ValidationError("Category move would create a cycle")
    if (0 if parent is None else _category_depth(parent)) + _subtree_height(locked) > 5:
        raise ValidationError("Category trees are limited to five levels")
    locked.parent = parent
    locked._allow_reparent = True
    locked.save(update_fields=["parent"])
    return locked


@transaction.atomic
def activate_product(*, product):
    locked = Product.objects.select_for_update().get(pk=product.pk)
    if not locked.variants.filter(is_active=True).exists():
        raise ValidationError("A sellable product requires at least one active variant")
    locked.is_active = True
    locked.is_sellable = True
    locked.save(update_fields=["is_active", "is_sellable"])
    return locked


@transaction.atomic
def set_variant_active(*, variant, active):
    locked = ProductVariant.objects.select_for_update().select_related("product").get(pk=variant.pk)
    Product.objects.select_for_update().get(pk=locked.product_id)
    if (
        not active
        and locked.is_active
        and locked.product.is_sellable
        and not locked.product.variants.filter(is_active=True).exclude(pk=locked.pk).exists()
    ):
        raise ValidationError("Cannot deactivate the last active variant")
    locked.is_active = active
    locked._allow_state_change = True
    locked.save(update_fields=["is_active"])
    return locked


@transaction.atomic
def delete_variant(*, variant):
    locked = ProductVariant.objects.select_for_update().select_related("product").get(pk=variant.pk)
    Product.objects.select_for_update().get(pk=locked.product_id)
    if (
        locked.is_active
        and locked.product.is_sellable
        and not locked.product.variants.filter(is_active=True).exclude(pk=locked.pk).exists()
    ):
        raise ValidationError("Cannot delete the last active variant")
    locked._allow_delete = True
    locked.delete()
